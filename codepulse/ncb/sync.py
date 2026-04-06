"""NCBSync — high-level cloud sync operations for CodePulse.

All methods are fire-and-forget: call with run_worker() or await directly.
Never raises — NCB is non-blocking backup, not critical path.
"""
from __future__ import annotations

import traceback
from typing import Optional

from codepulse.ncb.client import NCBClient


class NCBSync:
    def __init__(self) -> None:
        self._client = NCBClient()

    # ── Session & turn backup ────────────────────────────────────────────────

    async def sync_session(
        self,
        *,
        project_name: str,
        session_date: str,
        turn_count: int,
        claude_session_id: Optional[str],
        agent_slot: int,
    ) -> None:
        await self._client.create("sessions", {
            "project_name": project_name,
            "session_date": session_date,
            "turn_count": turn_count,
            "claude_session_id": claude_session_id or "",
            "agent_slot": agent_slot,
        })

    async def sync_turn(
        self,
        *,
        project_name: str,
        turn_index: int,
        user_message: str,
        assistant_message: str,
        synopsis: str,
        agent_slot: int,
        files_changed: int = 0,
        lines_added: int = 0,
        lines_removed: int = 0,
    ) -> None:
        await self._client.create("turns", {
            "project_name": project_name,
            "turn_index": turn_index,
            "user_message": user_message[:2000],
            "assistant_message": assistant_message[:4000],
            "synopsis": synopsis[:1000],
            "agent_slot": agent_slot,
            "files_changed": files_changed,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
        })

    # ── Self-healing: error log ──────────────────────────────────────────────

    async def log_error(
        self,
        *,
        project_name: str,
        error_type: str,
        error_message: str,
        context: str = "",
        exc: Optional[BaseException] = None,
    ) -> None:
        tb_str = (
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            if exc else ""
        )
        await self._client.create("errors", {
            "project_name": project_name,
            "error_type": error_type,
            "error_message": error_message[:500],
            "traceback": tb_str[:2000],
            "context": context[:500],
            "resolved": False,
        })

    async def get_unresolved_errors(self, project_name: str) -> list[dict]:
        """Return open error records for this project (used at startup)."""
        return await self._client.read(
            "errors",
            filters={"project_name": project_name, "resolved": "false"},
            limit=20,
        )

    async def resolve_error(self, error_id: str) -> None:
        await self._client.update("errors", error_id, {"resolved": True})

    # ── Insights ─────────────────────────────────────────────────────────────

    async def save_insight(
        self,
        *,
        project_name: str,
        content: str,
        source_turn: int,
        category: str = "general",
    ) -> None:
        await self._client.create("insights", {
            "project_name": project_name,
            "content": content[:2000],
            "source_turn": source_turn,
            "category": category,
        })

    # ── Pinned content ───────────────────────────────────────────────────────

    async def pin_content(
        self,
        *,
        project_name: str,
        content: str,
        label: str,
        source_turn: int = 0,
    ) -> None:
        await self._client.create("pinned", {
            "project_name": project_name,
            "content": content[:4000],
            "label": label[:200],
            "source_turn": source_turn,
        })

    # ── Quick action history ─────────────────────────────────────────────────

    async def record_action(
        self,
        *,
        project_name: str,
        action_id: str,
        action_label: str,
        prompt: str,
    ) -> None:
        await self._client.create("action_history", {
            "project_name": project_name,
            "action_id": action_id,
            "action_label": action_label,
            "prompt": prompt[:500],
        })
