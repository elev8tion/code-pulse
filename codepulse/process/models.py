"""Process management data models."""
from __future__ import annotations

from collections import deque
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProcessStatus(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    ERROR   = "error"


class ProcessRecord(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    name: str
    command: str
    status: ProcessStatus = ProcessStatus.STOPPED
    pid: Optional[int] = None
    exit_code: Optional[int] = None
    # Runtime-only ring buffer — not serialized
    output_lines: Any = Field(default_factory=lambda: deque(maxlen=200), exclude=True)
