"""CodePulseApp — main Textual application and orchestrator."""
from __future__ import annotations

import asyncio
import atexit
import os
from pathlib import Path
from typing import Optional

_PID_FILE = Path.home() / ".codepulse" / "running.pid"

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, TabbedContent

from codepulse.agents.discussion import DiscussionSession
from codepulse.agents.pool import SubAgentPool
from codepulse.api.claude_client import DispatchClient
from codepulse.config import AGENT_POOL_SIZE, CLAUDE_MODEL, SYNOPSIS_MODEL
from codepulse.git.parser import UnifiedDiffParser
from codepulse.git.tracker import DiffTracker
from codepulse.heatmap.aggregator import HeatMapAggregator
from codepulse.process.detector import ProjectDetector
from codepulse.process.models import ProcessStatus
from codepulse.process.runner import ProcessRunner
from codepulse.session.exporter import MarkdownExporter
from codepulse.session.manager import SessionManager
from codepulse.session.models import Session
from codepulse.utils.paths import diffs_dir, heatmaps_dir
from codepulse.utils.time_utils import today_str
from codepulse.ncb.sync import NCBSync
from codepulse.widgets.bottom_drawer import BottomDrawer
from codepulse.widgets.chat_panel import ChatPanel
from codepulse.widgets.diff_panel import DiffPanel
from codepulse.widgets.heatmap_panel import HeatMapPanel
from codepulse.widgets.process_manager import ProcessManager
from codepulse.widgets.prompt_input import PromptInput
from codepulse.widgets.quick_actions import ActionCard, QuickActionDeck, write_default_actions
from codepulse.widgets.status_bar import StatusBar
from codepulse.widgets.tool_palette import ToolPalette


# ── Sub-prompt modal ─────────────────────────────────────────────────────────

class SubPromptModal(ModalScreen[str]):
    """Modal for actions that need extra input (e.g. Scaffold Feature)."""

    DEFAULT_CSS = """
    SubPromptModal {
        align: center middle;
    }
    SubPromptModal > #modal-box {
        width: 60;
        height: 9;
        border: solid $accent;
        background: #1a1a2e;
        padding: 1 2;
        layout: vertical;
    }
    SubPromptModal > #modal-box > Label {
        height: 1;
        margin-bottom: 1;
    }
    SubPromptModal > #modal-box > Input {
        height: 3;
    }
    SubPromptModal > #modal-box > #modal-hint {
        height: 1;
        color: $text-muted;
        margin-top: 1;
    }
    """

    def __init__(self, prompt_label: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._label = prompt_label

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-box"):
            yield Label(self._label)
            yield Input(id="modal-input")
            yield Label("[dim]Enter to confirm  •  Esc to cancel[/dim]", id="modal-hint")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss("")


# ── Main App ─────────────────────────────────────────────────────────────────

class CodePulseApp(App):
    CSS_PATH = "styles/app.tcss"
    TITLE = "CodePulse"

    BINDINGS = [
        Binding("ctrl+q", "quit",          "Quit",     priority=True),
        Binding("ctrl+d", "toggle_discuss","Discuss"),
        Binding("ctrl+b", "toggle_drawer", "Drawer"),
        Binding("ctrl+e", "export_session","Export"),
        Binding("ctrl+l", "clear_log",     "Clear"),
    ]

    def __init__(
        self,
        project_path: str,
        project_name: str,
        resume: bool = False,
    ) -> None:
        super().__init__()
        self._project_path = Path(project_path).resolve()
        self._project_name = project_name
        self._resume = resume
        self._cwd = str(self._project_path)

        self._claude = DispatchClient(model=CLAUDE_MODEL, synopsis_model=SYNOPSIS_MODEL)
        self._pool = SubAgentPool(size=AGENT_POOL_SIZE)
        self._aggregator = HeatMapAggregator()
        self._diff_tracker = DiffTracker(self._project_path, project_name)
        self._diff_parser = UnifiedDiffParser()
        self._session_mgr = SessionManager(project_name, self._project_path)
        self._session: Optional[Session] = None
        self._discussion: Optional[DiscussionSession] = None
        self._in_discuss_mode = False

        # Process runners: name → ProcessRunner
        self._runners: dict[str, ProcessRunner] = {}

        # NCB cloud sync (fire-and-forget, non-blocking)
        self._ncb = NCBSync()
        self._last_assistant_response: str = ""

    # ── Layout ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-layout"):
            with Vertical(id="left-column"):
                yield ChatPanel(id="chat-panel")
            with Vertical(id="right-column"):
                yield HeatMapPanel(id="heatmap-panel")
                yield DiffPanel(id="diff-panel")
        yield BottomDrawer(cwd=self._cwd, id="bottom-drawer")
        yield StatusBar(id="status-bar")

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def on_mount(self) -> None:
        # Let menu bar app know we're live
        _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PID_FILE.write_text(str(os.getpid()))
        atexit.register(lambda: _PID_FILE.unlink(missing_ok=True))

        write_default_actions()
        await self._initialize()

    async def _initialize(self) -> None:
        status = self._status_bar
        chat = self._chat_panel

        status.project_name = self._project_name
        status.session_date = today_str()
        status.agent_total = AGENT_POOL_SIZE
        status.agent_slot = 0

        await self._diff_tracker.initialize()
        status.is_git = self._diff_tracker.is_git_repo

        if self._resume:
            self._session = SessionManager.load_latest(self._project_name)
            if self._session is None:
                self._session = self._session_mgr.load_or_create()
                chat.write_system("No prior session found — starting fresh.")
            else:
                hm_dir = heatmaps_dir(self._project_name)
                self._aggregator = HeatMapAggregator.from_heatmap_files(hm_dir)
                self._pool.restore_slot(self._session.current_agent_slot)
                status.agent_slot = self._pool.current_slot
                self._heatmap_panel.heatmap_state = self._aggregator.to_state()
                session_id_info = (
                    f"  session: {self._session.claude_session_id[:8]}…"
                    if self._session.claude_session_id else ""
                )
                chat.write_system(
                    f"Resumed from {self._session.session_date} "
                    f"({self._session.turn_count} turns).{session_id_info}"
                )
        else:
            self._session = self._session_mgr.load_or_create()

        vcs = "git" if self._diff_tracker.is_git_repo else "snapshot"
        chat.write_system(
            f"Project: [bold]{self._project_name}[/bold]  Path: {self._cwd}  "
            f"VCS: {vcs}  •  [dim]Ctrl+B[/dim] toggles tool/process/action drawer"
        )

        # Auto-detect and load processes
        await self._load_detected_processes()

        # Self-healing: surface unresolved errors from previous sessions
        self.run_worker(self._check_unresolved_errors(), name="ncb_errors")

    async def _check_unresolved_errors(self) -> None:
        """On startup, fetch any unresolved errors from NCB and show in chat."""
        try:
            errors = await self._ncb.get_unresolved_errors(self._project_name)
            if errors:
                self._chat_panel.write_system(
                    f"[bold yellow]NCB:[/bold yellow] {len(errors)} unresolved error(s) from "
                    f"previous sessions. Use [dim]/pin[/dim] to save important context.",
                    style="yellow dim",
                )
        except Exception:
            pass

    async def _load_detected_processes(self) -> None:
        try:
            detector = ProjectDetector(self._project_path)
            records = detector.detect()
            pm = self._process_manager
            await pm.load_processes(records)

            # Build runners for each detected process
            for record in records:
                self._runners[record.name] = ProcessRunner(
                    record=record,
                    on_output=pm.output_callback,
                    on_status_change=self._on_process_status_change,
                )
            if records:
                self._chat_panel.write_system(
                    f"Detected {len(records)} runnable process(es). "
                    f"Open [dim]Ctrl+B → Processes[/dim] to manage them."
                )
        except Exception as e:
            self._chat_panel.write_system(f"Process detection error: {e}", style="dim red")

    # ── Widget accessors ─────────────────────────────────────────────────────

    @property
    def _chat_panel(self) -> ChatPanel:
        return self.query_one("#chat-panel", ChatPanel)

    @property
    def _diff_panel(self) -> DiffPanel:
        return self.query_one("#diff-panel", DiffPanel)

    @property
    def _heatmap_panel(self) -> HeatMapPanel:
        return self.query_one("#heatmap-panel", HeatMapPanel)

    @property
    def _status_bar(self) -> StatusBar:
        return self.query_one("#status-bar", StatusBar)

    @property
    def _bottom_drawer(self) -> BottomDrawer:
        return self.query_one("#bottom-drawer", BottomDrawer)

    @property
    def _tool_palette(self) -> ToolPalette:
        return self.query_one("#tool-palette", ToolPalette)

    @property
    def _process_manager(self) -> ProcessManager:
        return self.query_one("#process-manager", ProcessManager)

    @property
    def _quick_actions(self) -> QuickActionDeck:
        return self.query_one("#quick-actions", QuickActionDeck)

    # ── Event routing ─────────────────────────────────────────────────────────

    async def on_prompt_input_submitted(self, event: PromptInput.Submitted) -> None:
        if event.is_command:
            await self._handle_command(event.command, event.args)
        elif self._in_discuss_mode and self._discussion:
            await self._handle_discuss_message(event.text)
        else:
            await self._run_completion_cycle(event.text)

    async def on_action_card_fired(self, event: ActionCard.Fired) -> None:
        self.run_worker(
            self._ncb.record_action(
                project_name=self._project_name,
                action_id=event.action_id,
                action_label=event.label,
                prompt=event.prompt,
            ),
            name="ncb_action",
        )
        if event.needs_sub_prompt:
            result = await self.push_screen_wait(SubPromptModal(event.sub_prompt_label))
            if result:
                await self._run_completion_cycle(event.prompt + result)
        else:
            await self._run_completion_cycle(event.prompt)

    async def on_process_card_toggle_requested(
        self, event: "ProcessManager.ToggleRequested"  # type: ignore[name-defined]
    ) -> None:
        await self._toggle_process(event.name)

    async def on_process_manager_toggle_requested(
        self, event
    ) -> None:
        await self._toggle_process(event.name)

    async def _toggle_process(self, name: str) -> None:
        runner = self._runners.get(name)
        if runner is None:
            return
        if runner.is_running:
            await runner.stop()
        else:
            self.run_worker(runner.start(cwd=self._cwd), name=f"proc-{name}")

    def _on_process_status_change(self, name: str, status: ProcessStatus) -> None:
        running = sum(1 for r in self._runners.values() if r.is_running)
        self._status_bar.process_count = running

    async def _handle_command(self, command: Optional[str], args: str) -> None:
        chat = self._chat_panel
        drawer = self._bottom_drawer
        match command:
            case "/discuss":
                await self.action_toggle_discuss()
            case "/help":
                chat.write_help()
            case "/agents":
                self._show_agents_status()
            case "/clear":
                chat.clear_log()
            case "/export":
                await self.action_export_session()
            case "/exit":
                if self._in_discuss_mode:
                    await self.action_toggle_discuss()
            case "/pin":
                await self._pin_last_response(args)
            case "/tools":
                drawer.show_tab("tab-tools")
            case "/processes":
                drawer.show_tab("tab-processes")
            case "/actions":
                drawer.show_tab("tab-actions")
            case _:
                chat.write_system(f"Unknown command: {command}", style="red")

    # ── Completion cycle ──────────────────────────────────────────────────────

    async def _run_completion_cycle(self, user_message: str) -> None:
        assert self._session is not None
        chat = self._chat_panel
        status = self._status_bar

        chat.write_user(user_message)
        chat.begin_assistant_turn()
        status.status = "streaming"

        full_response = ""
        try:
            async for chunk in self._claude.stream_completion(
                prompt=user_message,
                session_id=self._session.claude_session_id,
                cwd=self._cwd,
                on_tool_call=self._on_tool_call,
            ):
                full_response += chunk
                chat.stream_chunk(chunk)
        except RuntimeError as e:
            chat.stream_chunk(f"\n[bold red]Error:[/bold red] {e}")
            full_response = str(e)
            self.run_worker(
                self._ncb.log_error(
                    project_name=self._project_name,
                    error_type="stream_runtime",
                    error_message=str(e),
                    context=f"prompt={user_message[:100]}",
                    exc=e,
                ),
                name="ncb_log_error",
            )
        except Exception as e:
            chat.stream_chunk(f"\n[Error: {e}]")
            full_response = str(e)
            self.run_worker(
                self._ncb.log_error(
                    project_name=self._project_name,
                    error_type="stream_error",
                    error_message=str(e),
                    context=f"prompt={user_message[:100]}",
                    exc=e,
                ),
                name="ncb_log_error",
            )

        self._last_assistant_response = full_response
        chat.end_assistant_turn()
        status.status = "processing"

        self.run_worker(
            self._post_completion(user_message, full_response),
            exclusive=False,
            name="post_completion",
        )

    async def _post_completion(self, user_message: str, assistant_response: str) -> None:
        assert self._session is not None
        status = self._status_bar
        chat = self._chat_panel
        current_slot = self._pool.current_slot
        dd = diffs_dir(self._project_name)
        hd = heatmaps_dir(self._project_name)
        turn_index = self._session.turn_count + 1
        captured_session_id = self._claude.last_session_id

        try:
            diff_text = await self._diff_tracker.capture_snapshot()
            diff_snapshot = self._diff_parser.parse(diff_text, turn_index)
            diff_path = await self._diff_tracker.save_diff(diff_text, turn_index, dd)

            chat.write_system(
                f"[Agent {current_slot + 1}] Processing changes...", style="dim yellow"
            )
            synopsis = await self._pool.current.run_post_completion(
                diff_text=diff_text,
                diff_snapshot=diff_snapshot,
                aggregator=self._aggregator,
                dispatch_client=self._claude,
                heatmaps_dir=hd,
                diffs_dir=dd,
                turn_index=turn_index,
                project_cwd=self._cwd,
            )
            heatmap_path = hd / f"{turn_index:03d}-heatmap.json"

            self._session_mgr.append_turn(
                session=self._session,
                user_msg=user_message,
                assistant_msg=assistant_response,
                diff_snapshot=diff_snapshot,
                synopsis=synopsis,
                agent_slot=current_slot,
                diff_path=diff_path,
                heatmap_path=heatmap_path,
                claude_session_id=captured_session_id,
            )

            self._pool.rotate(synopsis)
            self._session_mgr.record_handoff(
                self._session, current_slot, self._pool.current_slot, synopsis
            )
            self._session_mgr.save(self._session)

            self._heatmap_panel.heatmap_state = self._aggregator.to_state()
            status.agent_slot = self._pool.current_slot
            status.status = "ready"

            if diff_snapshot.files:
                await self._diff_panel.animate_snapshot(diff_snapshot)
            else:
                chat.write_system("No file changes detected.", style="dim")

            # Cloud backup: fire-and-forget, never blocks
            self.run_worker(
                self._ncb.sync_turn(
                    project_name=self._project_name,
                    turn_index=turn_index,
                    user_message=user_message,
                    assistant_message=assistant_response,
                    synopsis=synopsis,
                    agent_slot=current_slot,
                    files_changed=len(diff_snapshot.files),
                    lines_added=diff_snapshot.total_added,
                    lines_removed=diff_snapshot.total_removed,
                ),
                name="ncb_sync_turn",
            )
            self.run_worker(
                self._ncb.sync_session(
                    project_name=self._project_name,
                    session_date=self._session.session_date,
                    turn_count=self._session.turn_count,
                    claude_session_id=captured_session_id,
                    agent_slot=self._pool.current_slot,
                ),
                name="ncb_sync_session",
            )

        except Exception as e:
            chat.write_system(f"Post-completion error: {e}", style="red dim")
            status.status = "ready"
            self.run_worker(
                self._ncb.log_error(
                    project_name=self._project_name,
                    error_type="post_completion",
                    error_message=str(e),
                    context=f"turn={turn_index}",
                    exc=e,
                ),
                name="ncb_log_error",
            )

    # ── Tool call callback ────────────────────────────────────────────────────

    def _on_tool_call(self, tool_name: str) -> None:
        """Called in real-time from the stream as Claude uses a tool."""
        try:
            self._tool_palette.activate_tool(tool_name)
            self._status_bar.last_tool = tool_name
            self.set_timer(5.0, self._clear_last_tool)
        except Exception:
            pass

    def _clear_last_tool(self) -> None:
        self._status_bar.last_tool = ""

    # ── Discussion mode ───────────────────────────────────────────────────────

    async def action_toggle_discuss(self) -> None:
        chat = self._chat_panel
        status = self._status_bar

        if self._in_discuss_mode:
            if self._discussion:
                self._discussion.close()
                self._discussion = None
            self._in_discuss_mode = False
            status.status = "ready"
            chat.write_discuss_close()
        else:
            self._discussion = DiscussionSession(
                agent=self._pool.current,
                dispatch_client=self._claude,
                project_cwd=self._cwd,
            )
            self._in_discuss_mode = True
            status.status = "discussing"
            preview = self._discussion.open()
            chat.write_discuss_open(self._pool.current_slot, preview)

    async def _handle_discuss_message(self, user_message: str) -> None:
        assert self._discussion is not None
        chat = self._chat_panel

        chat.write_user(user_message)
        chat.begin_agent_turn(self._discussion.agent_slot)

        try:
            async for chunk in self._discussion.send(user_message):
                chat.stream_chunk(chunk)
        except Exception as e:
            chat.stream_chunk(f"\n[Error: {e}]")

        chat.stream_chunk("\n")

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_toggle_drawer(self) -> None:
        self._bottom_drawer.toggle()

    async def action_export_session(self) -> None:
        assert self._session is not None
        status = self._status_bar
        chat = self._chat_panel
        status.status = "exporting"

        try:
            export_path = self._project_path / f"codepulse-session-{self._session.session_date}.md"
            exporter = MarkdownExporter(self._session, self._session_mgr.session_dir)
            exporter.export(export_path)
            chat.write_system(f"Exported to: {export_path}", style="green")
        except Exception as e:
            chat.write_system(f"Export failed: {e}", style="red")
        finally:
            status.status = "ready"

    def action_clear_log(self) -> None:
        self._chat_panel.clear_log()

    async def _pin_last_response(self, label: str) -> None:
        """Pin the last assistant response to NCB cloud. /pin [optional label]"""
        chat = self._chat_panel
        if not self._last_assistant_response:
            chat.write_system("Nothing to pin yet.", style="dim")
            return
        turn_index = self._session.turn_count if self._session else 0
        effective_label = label.strip() or f"Turn {turn_index}"
        self.run_worker(
            self._ncb.pin_content(
                project_name=self._project_name,
                content=self._last_assistant_response,
                label=effective_label,
                source_turn=turn_index,
            ),
            name="ncb_pin",
        )
        chat.write_system(f"Pinned to cloud: [bold]{effective_label}[/bold]", style="green")

    def _show_agents_status(self) -> None:
        chat = self._chat_panel
        lines = ["\n[bold]Subagent Pool Status:[/bold]"]
        for agent in self._pool.all_agents():
            marker = "►" if agent.slot_id == self._pool.current_slot else " "
            synopsis_preview = agent.synopsis[:80].replace("\n", " ") if agent.synopsis else "—"
            lines.append(
                f"  {marker} Agent {agent.slot_id + 1}  [{agent.state.value}]  {synopsis_preview}"
            )
        chat.write_system("\n".join(lines))
