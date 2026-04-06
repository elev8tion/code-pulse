"""Tests for HeatMapAggregator."""
import pytest
from codepulse.git.parser import DiffSnapshot, FileDiff
from codepulse.heatmap.aggregator import HeatMapAggregator


def make_snapshot(files):
    return DiffSnapshot(
        turn_index=1,
        raw_text="",
        files=files,
        total_added=sum(f.lines_added for f in files),
        total_removed=sum(f.lines_removed for f in files),
        directories_affected=list({f.directory for f in files}),
    )


def test_ingest_basic():
    agg = HeatMapAggregator()
    snap = make_snapshot([
        FileDiff(path="src/app.py", change_type="modified", lines_added=10, lines_removed=2, directory="src"),
        FileDiff(path="tests/test_app.py", change_type="added", lines_added=20, lines_removed=0, directory="tests"),
    ])
    agg.ingest(snap)
    state = agg.to_state()
    assert "src/app.py" in state.entries
    assert state.entries["src/app.py"].touch_count == 1
    assert state.entries["src/app.py"].lines_changed == 12


def test_normalize_intensity():
    agg = HeatMapAggregator()
    snap = make_snapshot([
        FileDiff(path="a.py", change_type="modified", lines_added=100, lines_removed=0, directory="."),
        FileDiff(path="b.py", change_type="modified", lines_added=10, lines_removed=0, directory="."),
    ])
    agg.ingest(snap)
    agg.normalize()
    state = agg.to_state()
    assert state.entries["a.py"].intensity > state.entries["b.py"].intensity
    assert state.entries["a.py"].intensity <= 1.0


def test_empty_ingest():
    agg = HeatMapAggregator()
    snap = make_snapshot([])
    agg.ingest(snap)
    agg.normalize()
    assert agg.to_state().entries == {}
