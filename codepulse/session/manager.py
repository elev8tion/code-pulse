"""SessionManager — load, save, and resume sessions."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from codepulse.git.parser import DiffSnapshot
from codepulse.session.models import Session, SubagentHandoff, TurnRecord
from codepulse.utils.paths import diffs_dir, heatmaps_dir, project_dir, session_file, list_projects
from codepulse.utils.time_utils import now_utc, today_str


class SessionManager:
    def __init__(self, project_name: str, project_path: Path) -> None:
        self._project_name = project_name
        self._project_path = project_path

    @property
    def project_name(self) -> str:
        return self._project_name

    @property
    def session_dir(self) -> Path:
        return project_dir(self._project_name)

    @property
    def diffs_dir(self) -> Path:
        return diffs_dir(self._project_name)

    @property
    def heatmaps_dir(self) -> Path:
        return heatmaps_dir(self._project_name)

    def load_or_create(self) -> Session:
        """Load today's session or create a fresh one."""
        sf = session_file(self._project_name, today_str())
        if sf.exists():
            try:
                return Session.model_validate_json(sf.read_text())
            except Exception:
                pass
        return Session(
            project_name=self._project_name,
            project_path=str(self._project_path),
        )

    def save(self, session: Session) -> None:
        sf = session_file(self._project_name, session.session_date)
        sf.write_text(session.model_dump_json(indent=2))

    def append_turn(
        self,
        session: Session,
        user_msg: str,
        assistant_msg: str,
        diff_snapshot: Optional[DiffSnapshot],
        synopsis: str,
        agent_slot: int,
        diff_path: Optional[Path] = None,
        heatmap_path: Optional[Path] = None,
        claude_session_id: Optional[str] = None,
    ) -> TurnRecord:
        turn_index = session.turn_count + 1
        turn = TurnRecord(
            turn_index=turn_index,
            timestamp=now_utc(),
            user_message=user_msg,
            assistant_message=assistant_msg,
            diff_path=str(diff_path) if diff_path else None,
            heatmap_path=str(heatmap_path) if heatmap_path else None,
            agent_slot=agent_slot,
            synopsis=synopsis,
        )
        session.turns.append(turn)

        # Persist the Claude Code session ID so --resume works on next turn
        if claude_session_id:
            session.claude_session_id = claude_session_id

        return turn

    def record_handoff(
        self, session: Session, from_slot: int, to_slot: int, synopsis: str
    ) -> None:
        handoff = SubagentHandoff(
            from_slot=from_slot,
            to_slot=to_slot,
            synopsis=synopsis,
            timestamp=now_utc(),
        )
        session.handoffs.append(handoff)
        session.current_agent_slot = to_slot

    @classmethod
    def list_projects(cls) -> list[dict]:
        """Return list of {name, sessions, latest_date} dicts."""
        result = []
        for name in list_projects():
            pd = project_dir(name)
            sessions = sorted(pd.glob("session-*.json"))
            latest = sessions[-1].stem.replace("session-", "") if sessions else "—"
            result.append({
                "name": name,
                "session_count": len(sessions),
                "latest": latest,
            })
        return result

    @classmethod
    def load_latest(cls, project_name: str) -> Optional[Session]:
        """Load the most recent session for a project."""
        pd = project_dir(project_name)
        sessions = sorted(pd.glob("session-*.json"))
        if not sessions:
            return None
        try:
            return Session.model_validate_json(sessions[-1].read_text())
        except Exception:
            return None
