"""
CodePulse FastAPI server — bridges all backend modules to the web frontend.

Starts with:
    uvicorn codepulse.server:app --host 0.0.0.0 --port 3000

Provides:
  - WebSocket /ws  — real-time streaming of Claude output, tool events,
                     process status, heatmap updates
  - REST endpoints for prompt submission, session state, heatmap, agents,
    processes, discussion, export, actions, and slash commands
  - Static file serving for the compiled frontend (frontend/dist/)
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from codepulse.agents.discussion import DiscussionSession
from codepulse.agents.pool import SubAgentPool
from codepulse.api.claude_client import DispatchClient
from codepulse.config import AGENT_POOL_SIZE, AGENT_CONTEXT_WINDOW
from codepulse.git.parser import UnifiedDiffParser
from codepulse.git.tracker import DiffTracker
from codepulse.heatmap.aggregator import HeatMapAggregator
from codepulse.process.detector import ProjectDetector
from codepulse.process.models import ProcessRecord, ProcessStatus
from codepulse.process.runner import ProcessRunner
from codepulse.session.exporter import MarkdownExporter
from codepulse.session.manager import SessionManager
from codepulse.session.models import Session
from codepulse.widgets.quick_actions import _load_actions, ActionDefinition
from codepulse.ncb.sync import NCBSync
from codepulse.utils.paths import project_dir


# ── Global application state ─────────────────────────────────────────────────

class AppState:
    """Holds all runtime objects for the lifetime of the server process."""

    def __init__(self) -> None:
        # Resolved from CLI args or environment
        self.project_path: str = os.environ.get("CODEPULSE_PROJECT_PATH", str(Path.cwd()))
        self.project_name: str = os.environ.get(
            "CODEPULSE_PROJECT_NAME",
            Path(self.project_path).resolve().name or "project",
        )

        # Backend singletons
        self.dispatch_client = DispatchClient()
        self.agent_pool = SubAgentPool(size=AGENT_POOL_SIZE, context_window_size=AGENT_CONTEXT_WINDOW)
        self.aggregator = HeatMapAggregator()
        self.diff_tracker = DiffTracker(Path(self.project_path), self.project_name)
        self.diff_parser = UnifiedDiffParser()
        self.session_manager = SessionManager(self.project_name, Path(self.project_path))
        self.ncb_sync = NCBSync()

        # Session + discussion
        self.session: Optional[Session] = None
        self.discussion: Optional[DiscussionSession] = None

        # Process runners: name → ProcessRunner
        self.process_runners: dict[str, ProcessRunner] = {}

        # WebSocket connections
        self.connections: list[WebSocket] = []

        # Whether the system is currently streaming a Claude response
        self.is_streaming = False

        # Active tools tracking (tool_name → count)
        self.active_tools: dict[str, int] = {}

    async def initialize(self, resume: bool = False) -> None:
        """Called once at startup to bootstrap state."""
        self.session_manager._project_path.mkdir(parents=True, exist_ok=True)
        await self.diff_tracker.initialize()

        if resume:
            s = SessionManager.load_latest(self.project_name)
            self.session = s or self.session_manager.load_or_create()
            if self.session.claude_session_id:
                self.dispatch_client.last_session_id = self.session.claude_session_id
            if self.session.current_agent_slot:
                self.agent_pool.restore_slot(self.session.current_agent_slot)
            # Restore heatmap
            from codepulse.heatmap.aggregator import HeatMapAggregator as HMA
            from codepulse.utils.paths import heatmaps_dir as hd
            self.aggregator = HMA.from_heatmap_files(hd(self.project_name))
        else:
            self.session = self.session_manager.load_or_create()

        # Detect project processes
        detector = ProjectDetector(Path(self.project_path))
        records = detector.detect()
        for record in records:
            self.process_runners[record.name] = ProcessRunner(
                record=record,
                on_output=self._on_process_output,
                on_status_change=self._on_process_status_change,
            )

    def _on_process_output(self, name: str, line: str) -> None:
        asyncio.create_task(self.broadcast({
            "type": "process_output",
            "name": name,
            "line": line,
        }))

    def _on_process_status_change(self, name: str, status: ProcessStatus) -> None:
        asyncio.create_task(self.broadcast({
            "type": "process_status",
            "name": name,
            "status": status.value,
        }))

    async def broadcast(self, message: dict) -> None:
        """Send JSON message to all connected WebSocket clients."""
        dead: list[WebSocket] = []
        payload = json.dumps(message)
        for ws in list(self.connections):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.connections:
                self.connections.remove(ws)


# Singleton application state
state = AppState()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    resume = os.environ.get("CODEPULSE_RESUME", "0") == "1"
    await state.initialize(resume=resume)
    yield


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="CodePulse", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    state.connections.append(websocket)
    # Send current state snapshot immediately
    await _send_snapshot(websocket)
    try:
        while True:
            # Keep alive — actual events are pushed by broadcast()
            await asyncio.sleep(15)
            try:
                await websocket.send_text(json.dumps({"type": "ping"}))
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in state.connections:
            state.connections.remove(websocket)


async def _send_snapshot(ws: WebSocket) -> None:
    """Push full state snapshot to a newly connected client."""
    snap = _build_state_snapshot()
    try:
        await ws.send_text(json.dumps({"type": "snapshot", "data": snap}))
    except Exception:
        pass


def _build_state_snapshot() -> dict:
    assert state.session is not None
    return {
        "project_name": state.project_name,
        "project_path": state.project_path,
        "session_date": state.session.session_date,
        "turn_count": state.session.turn_count,
        "current_agent_slot": state.agent_pool.current_slot,
        "agent_pool_size": state.agent_pool.size,
        "is_streaming": state.is_streaming,
        "heatmap": _heatmap_payload(),
        "agents": _agents_payload(),
        "processes": _processes_payload(),
        "recent_turns": _recent_turns_payload(),
        "handoffs": _handoffs_payload(),
    }


# ── REST API ──────────────────────────────────────────────────────────────────

# -- Prompt -------------------------------------------------------------------

class PromptRequest(BaseModel):
    message: str


@app.post("/api/prompt")
async def post_prompt(req: PromptRequest) -> JSONResponse:
    """Send a user message and stream response via WebSocket."""
    if state.is_streaming:
        return JSONResponse({"error": "Already streaming"}, status_code=429)
    if not state.session:
        return JSONResponse({"error": "Session not initialized"}, status_code=500)

    asyncio.create_task(_run_completion(req.message))
    return JSONResponse({"status": "streaming"})


async def _run_completion(user_message: str) -> None:
    assert state.session is not None
    state.is_streaming = True
    full_response: list[str] = []

    await state.broadcast({"type": "stream_start", "user_message": user_message})

    try:
        async for chunk in state.dispatch_client.stream_completion(
            prompt=user_message,
            session_id=state.dispatch_client.last_session_id,
            cwd=state.project_path,
            on_tool_call=_handle_tool_call,
        ):
            full_response.append(chunk)
            await state.broadcast({"type": "stream_chunk", "text": chunk})

        assistant_message = "".join(full_response)

        # Post-completion: diff → heatmap → synopsis
        diff_text = await state.diff_tracker.capture_snapshot()
        snapshot = state.diff_parser.parse(diff_text, state.session.turn_count + 1)

        pd = project_dir(state.project_name)
        heatmaps_path = pd / "heatmaps"
        diffs_path = pd / "diffs"
        heatmaps_path.mkdir(exist_ok=True)
        diffs_path.mkdir(exist_ok=True)

        current_agent = state.agent_pool.current
        synopsis = await current_agent.run_post_completion(
            diff_text=diff_text,
            diff_snapshot=snapshot,
            aggregator=state.aggregator,
            dispatch_client=state.dispatch_client,
            heatmaps_dir=heatmaps_path,
            diffs_dir=diffs_path,
            turn_index=state.session.turn_count + 1,
            project_cwd=state.project_path,
        )

        diff_path = await state.diff_tracker.save_diff(
            diff_text, state.session.turn_count + 1, diffs_path
        ) if diff_text else None

        # Persist turn
        turn = state.session_manager.append_turn(
            session=state.session,
            user_msg=user_message,
            assistant_msg=assistant_message,
            diff_snapshot=snapshot,
            synopsis=synopsis,
            agent_slot=state.agent_pool.current_slot,
            diff_path=diff_path,
            claude_session_id=state.dispatch_client.last_session_id,
        )
        state.session_manager.save(state.session)

        # Rotate agent pool
        prev_slot = state.agent_pool.current_slot
        state.agent_pool.rotate(synopsis)
        state.session_manager.record_handoff(
            state.session, prev_slot, state.agent_pool.current_slot, synopsis
        )
        state.session_manager.save(state.session)

        await state.broadcast({
            "type": "stream_end",
            "turn_index": turn.turn_index,
            "synopsis": synopsis,
            "agent_slot": prev_slot,
            "next_agent_slot": state.agent_pool.current_slot,
            "diff": {
                "files_changed": len(snapshot.files),
                "lines_added": snapshot.total_added,
                "lines_removed": snapshot.total_removed,
                "files": [f.model_dump() for f in snapshot.files[:10]],
            },
            "heatmap": _heatmap_payload(),
        })

        # Fire-and-forget NCB sync
        asyncio.create_task(_ncb_sync_turn(turn, snapshot))

    except Exception as exc:
        await state.broadcast({
            "type": "error",
            "message": str(exc),
        })
    finally:
        state.is_streaming = False
        state.active_tools.clear()
        await state.broadcast({"type": "tools_cleared"})


def _handle_tool_call(tool_name: str) -> None:
    state.active_tools[tool_name] = state.active_tools.get(tool_name, 0) + 1
    asyncio.create_task(state.broadcast({
        "type": "tool_call",
        "tool": tool_name,
        "count": state.active_tools[tool_name],
    }))


async def _ncb_sync_turn(turn, snapshot) -> None:
    try:
        await state.ncb_sync.sync_turn(
            project_name=state.project_name,
            turn_index=turn.turn_index,
            user_message=turn.user_message,
            assistant_message=turn.assistant_message,
            synopsis=turn.synopsis,
            agent_slot=turn.agent_slot,
            files_changed=len(snapshot.files),
            lines_added=snapshot.total_added,
            lines_removed=snapshot.total_removed,
        )
    except Exception:
        pass


# -- Session ------------------------------------------------------------------

@app.get("/api/session")
async def get_session() -> JSONResponse:
    if not state.session:
        return JSONResponse({"error": "No active session"}, status_code=404)
    return JSONResponse({
        "project_name": state.project_name,
        "project_path": state.project_path,
        "session_date": state.session.session_date,
        "turn_count": state.session.turn_count,
        "current_agent_slot": state.agent_pool.current_slot,
        "agent_pool_size": state.agent_pool.size,
        "is_streaming": state.is_streaming,
        "recent_turns": _recent_turns_payload(),
        "handoffs": _handoffs_payload(),
    })


# -- Heatmap ------------------------------------------------------------------

@app.get("/api/heatmap")
async def get_heatmap() -> JSONResponse:
    return JSONResponse(_heatmap_payload())


def _heatmap_payload() -> dict:
    hm_state = state.aggregator.to_state()
    entries = [
        {
            "path": e.path,
            "touch_count": e.touch_count,
            "lines_changed": e.lines_changed,
            "intensity": e.intensity,
        }
        for e in sorted(hm_state.entries.values(), key=lambda x: x.intensity, reverse=True)[:30]
    ]
    return {
        "entries": entries,
        "max_touch_count": hm_state.max_touch_count,
        "max_lines_changed": hm_state.max_lines_changed,
    }


# -- Agents -------------------------------------------------------------------

@app.get("/api/agents")
async def get_agents() -> JSONResponse:
    return JSONResponse(_agents_payload())


def _agents_payload() -> list[dict]:
    return [
        {
            "slot_id": a.slot_id,
            "state": a.state.value,
            "synopsis": a.synopsis,
            "is_current": a.slot_id == state.agent_pool.current_slot,
        }
        for a in state.agent_pool.all_agents()
    ]


# -- Processes ----------------------------------------------------------------

@app.get("/api/processes")
async def get_processes() -> JSONResponse:
    return JSONResponse(_processes_payload())


def _processes_payload() -> list[dict]:
    result = []
    for name, runner in state.process_runners.items():
        rec = runner.record
        result.append({
            "name": rec.name,
            "command": rec.command,
            "status": rec.status.value,
            "pid": rec.pid,
            "exit_code": rec.exit_code,
            "recent_output": list(rec.output_lines)[-20:],
        })
    return result


@app.post("/api/process/{name}/toggle")
async def toggle_process(name: str) -> JSONResponse:
    runner = state.process_runners.get(name)
    if not runner:
        return JSONResponse({"error": f"Process '{name}' not found"}, status_code=404)
    if runner.is_running:
        await runner.stop()
    else:
        asyncio.create_task(runner.start(cwd=state.project_path))
    return JSONResponse({"name": name, "status": runner.record.status.value})


# -- Discussion ---------------------------------------------------------------

@app.post("/api/discuss/toggle")
async def toggle_discuss() -> JSONResponse:
    if state.discussion and state.discussion.is_active:
        state.discussion.close()
        state.discussion = None
        await state.broadcast({"type": "discuss_closed"})
        return JSONResponse({"active": False})
    else:
        session_obj = DiscussionSession(
            agent=state.agent_pool.current,
            dispatch_client=state.dispatch_client,
            project_cwd=state.project_path,
        )
        preview = session_obj.open()
        state.discussion = session_obj
        await state.broadcast({"type": "discuss_opened", "synopsis_preview": preview})
        return JSONResponse({"active": True, "synopsis_preview": preview})


class DiscussMessage(BaseModel):
    message: str


@app.post("/api/discuss/message")
async def post_discuss_message(req: DiscussMessage) -> JSONResponse:
    if not state.discussion or not state.discussion.is_active:
        return JSONResponse({"error": "Discussion not active"}, status_code=400)

    asyncio.create_task(_run_discussion(req.message))
    return JSONResponse({"status": "streaming"})


async def _run_discussion(user_message: str) -> None:
    assert state.discussion is not None
    await state.broadcast({"type": "discuss_start", "user_message": user_message})
    try:
        async for chunk in state.discussion.send(user_message):
            await state.broadcast({"type": "discuss_chunk", "text": chunk})
    except Exception as exc:
        await state.broadcast({"type": "error", "message": str(exc)})
    finally:
        await state.broadcast({"type": "discuss_end"})


# -- Export -------------------------------------------------------------------

@app.post("/api/export")
async def export_session() -> JSONResponse:
    if not state.session:
        return JSONResponse({"error": "No session"}, status_code=404)
    from datetime import datetime
    export_path = Path.cwd() / f"codepulse-{state.project_name}-{state.session.session_date}.md"
    pd = project_dir(state.project_name)
    exporter = MarkdownExporter(state.session, pd)
    exporter.export(export_path)
    return JSONResponse({"path": str(export_path)})


# -- Actions ------------------------------------------------------------------

@app.get("/api/actions")
async def get_actions() -> JSONResponse:
    actions = _load_actions()
    return JSONResponse([_action_dict(a) for a in actions])


def _action_dict(a: ActionDefinition) -> dict:
    return {
        "id": a.id,
        "label": a.label,
        "icon": a.icon,
        "prompt": a.prompt,
        "needs_sub_prompt": a.needs_sub_prompt,
        "sub_prompt_label": a.sub_prompt_label,
        "color": a.color,
    }


class ActionFireRequest(BaseModel):
    sub_prompt: Optional[str] = None


@app.post("/api/action/{action_id}")
async def fire_action(action_id: str, req: ActionFireRequest) -> JSONResponse:
    if state.is_streaming:
        return JSONResponse({"error": "Already streaming"}, status_code=429)
    actions = {a.id: a for a in _load_actions()}
    action = actions.get(action_id)
    if not action:
        return JSONResponse({"error": "Unknown action"}, status_code=404)

    prompt = action.prompt or ""
    if action.needs_sub_prompt and req.sub_prompt:
        prompt = f"{prompt}{req.sub_prompt}"

    asyncio.create_task(_run_completion(prompt))
    return JSONResponse({"status": "streaming", "prompt": prompt})


# -- Commands -----------------------------------------------------------------

class CommandRequest(BaseModel):
    command: str


@app.post("/api/command")
async def post_command(req: CommandRequest) -> JSONResponse:
    cmd = req.command.strip()
    if cmd == "/help":
        return JSONResponse({"response": _help_text()})
    elif cmd == "/clear":
        if state.session:
            state.session.turns.clear()
            state.session_manager.save(state.session)
        return JSONResponse({"response": "Session history cleared."})
    elif cmd == "/discuss":
        result = await toggle_discuss()
        return result
    elif cmd == "/export":
        return await export_session()
    elif cmd.startswith("/pin "):
        content = cmd[5:].strip()
        asyncio.create_task(_pin_content(content))
        return JSONResponse({"response": f"Pinned: {content[:80]}"})
    else:
        return JSONResponse({"response": f"Unknown command: {cmd}"}, status_code=400)


async def _pin_content(content: str) -> None:
    try:
        turn_index = state.session.turn_count if state.session else 0
        await state.ncb_sync.pin_content(
            project_name=state.project_name,
            content=content,
            label=content[:80],
            source_turn=turn_index,
        )
    except Exception:
        pass


def _help_text() -> str:
    return (
        "Available commands:\n"
        "/help — show this help\n"
        "/clear — clear session history\n"
        "/discuss — toggle discussion mode\n"
        "/export — export session as markdown\n"
        "/pin <text> — pin content to cloud\n"
    )


# -- Session list/load --------------------------------------------------------

@app.get("/api/projects")
async def list_projects() -> JSONResponse:
    projects = SessionManager.list_projects()
    return JSONResponse(projects)


# ── Helper payloads ───────────────────────────────────────────────────────────

def _recent_turns_payload() -> list[dict]:
    if not state.session:
        return []
    turns = state.session.turns[-10:]
    return [
        {
            "turn_index": t.turn_index,
            "timestamp": t.timestamp.isoformat(),
            "user_message": t.user_message[:200],
            "assistant_message": t.assistant_message[:500],
            "synopsis": t.synopsis,
            "agent_slot": t.agent_slot,
            "diff_path": t.diff_path,
        }
        for t in turns
    ]


def _handoffs_payload() -> list[dict]:
    if not state.session:
        return []
    handoffs = state.session.handoffs[-20:]
    return [
        {
            "from_slot": h.from_slot,
            "to_slot": h.to_slot,
            "synopsis": h.synopsis[:200],
            "timestamp": h.timestamp.isoformat(),
        }
        for h in handoffs
    ]


# ── Static file serving ───────────────────────────────────────────────────────

FRONTEND_DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "project": state.project_name})


def _setup_static_files() -> None:
    if FRONTEND_DIST_DIR.exists():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> FileResponse:
            # API routes are already handled above; all other paths serve the SPA
            index = FRONTEND_DIST_DIR / "index.html"
            return FileResponse(str(index))


_setup_static_files()
