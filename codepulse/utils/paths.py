"""Path helpers for ~/.codepulse storage."""
from pathlib import Path
from codepulse.config import PROJECTS_DIR


def project_dir(project_name: str) -> Path:
    d = PROJECTS_DIR / _sanitize(project_name)
    d.mkdir(parents=True, exist_ok=True)
    return d


def diffs_dir(project_name: str) -> Path:
    d = project_dir(project_name) / "diffs"
    d.mkdir(exist_ok=True)
    return d


def heatmaps_dir(project_name: str) -> Path:
    d = project_dir(project_name) / "heatmaps"
    d.mkdir(exist_ok=True)
    return d


def session_file(project_name: str, date_str: str) -> Path:
    return project_dir(project_name) / f"session-{date_str}.json"


def snapshot_file(project_name: str) -> Path:
    return project_dir(project_name) / "snapshot.json"


def list_projects() -> list[str]:
    if not PROJECTS_DIR.exists():
        return []
    return sorted(p.name for p in PROJECTS_DIR.iterdir() if p.is_dir())


def _sanitize(name: str) -> str:
    """Make name safe for use as a directory."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
