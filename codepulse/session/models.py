"""Session persistence models."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from codepulse.utils.time_utils import now_utc, today_str


class TurnRecord(BaseModel):
    turn_index: int
    timestamp: datetime
    user_message: str
    assistant_message: str
    diff_path: Optional[str] = None
    heatmap_path: Optional[str] = None
    agent_slot: int
    synopsis: str


class SubagentHandoff(BaseModel):
    from_slot: int
    to_slot: int
    synopsis: str
    timestamp: datetime


class Session(BaseModel):
    project_name: str
    project_path: str
    session_date: str = Field(default_factory=today_str)
    created_at: datetime = Field(default_factory=now_utc)
    turns: list[TurnRecord] = Field(default_factory=list)
    handoffs: list[SubagentHandoff] = Field(default_factory=list)
    # Claude Code CLI session ID — passed as --resume on subsequent turns
    claude_session_id: Optional[str] = None
    current_agent_slot: int = 0

    @property
    def turn_count(self) -> int:
        return len(self.turns)
