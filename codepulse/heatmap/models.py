"""Heat map data models."""
from pydantic import BaseModel, Field


class HeatMapEntry(BaseModel):
    path: str
    touch_count: int = 0
    lines_changed: int = 0
    intensity: float = 0.0  # 0.0–1.0, normalized across session


class HeatMapState(BaseModel):
    entries: dict[str, HeatMapEntry] = Field(default_factory=dict)
    max_touch_count: int = 0
    max_lines_changed: int = 0
