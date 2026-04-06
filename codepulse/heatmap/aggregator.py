"""HeatMapAggregator — accumulates file touch counts across session."""
from __future__ import annotations

import json
from pathlib import Path

import aiofiles

from codepulse.git.parser import DiffSnapshot
from codepulse.heatmap.models import HeatMapEntry, HeatMapState


class HeatMapAggregator:
    def __init__(self) -> None:
        self._entries: dict[str, HeatMapEntry] = {}

    def ingest(self, snapshot: DiffSnapshot) -> None:
        """Merge a DiffSnapshot into running totals."""
        for fd in snapshot.files:
            if fd.path not in self._entries:
                self._entries[fd.path] = HeatMapEntry(path=fd.path)
            entry = self._entries[fd.path]
            entry.touch_count += 1
            entry.lines_changed += fd.lines_added + fd.lines_removed

    def normalize(self) -> None:
        """Recalculate intensity as fraction of session maximum."""
        if not self._entries:
            return
        max_lines = max(e.lines_changed for e in self._entries.values()) or 1
        max_touch = max(e.touch_count for e in self._entries.values()) or 1
        for entry in self._entries.values():
            # Weight: 70% lines changed, 30% touch count
            line_score = entry.lines_changed / max_lines
            touch_score = entry.touch_count / max_touch
            entry.intensity = 0.7 * line_score + 0.3 * touch_score

    def to_state(self) -> HeatMapState:
        max_tc = max((e.touch_count for e in self._entries.values()), default=0)
        max_lc = max((e.lines_changed for e in self._entries.values()), default=0)
        return HeatMapState(
            entries=dict(self._entries),
            max_touch_count=max_tc,
            max_lines_changed=max_lc,
        )

    def load_state(self, state: HeatMapState) -> None:
        """Restore aggregator from persisted state (for session resume)."""
        self._entries = dict(state.entries)

    async def save(self, turn_index: int, heatmaps_dir: Path) -> Path:
        path = heatmaps_dir / f"{turn_index:03d}-heatmap.json"
        state = self.to_state()
        async with aiofiles.open(path, "w") as f:
            await f.write(state.model_dump_json(indent=2))
        return path

    @classmethod
    def from_heatmap_files(cls, heatmaps_dir: Path) -> "HeatMapAggregator":
        """Rebuild aggregator by replaying heatmap files (for resume)."""
        agg = cls()
        if not heatmaps_dir.exists():
            return agg
        files = sorted(heatmaps_dir.glob("*-heatmap.json"))
        if not files:
            return agg
        # Use the latest snapshot to restore state
        latest = files[-1]
        try:
            state = HeatMapState.model_validate_json(latest.read_text())
            agg.load_state(state)
        except Exception:
            pass
        return agg
