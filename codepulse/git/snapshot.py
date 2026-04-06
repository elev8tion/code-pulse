"""File snapshot for non-git projects."""
from __future__ import annotations

import json
import os
from pathlib import Path


IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".codepulse", ".DS_Store"}
IGNORE_EXTENSIONS = {".pyc", ".pyo", ".o", ".so", ".egg-info"}


class FileSnapshot:
    """Walk a directory and track {path: (mtime, size)} for non-git diffs."""

    def __init__(self, project_path: Path, snapshot_file: Path) -> None:
        self._root = project_path
        self._snapshot_file = snapshot_file
        self._prev: dict[str, tuple[float, int]] = {}

    def load(self) -> None:
        if self._snapshot_file.exists():
            try:
                data = json.loads(self._snapshot_file.read_text())
                self._prev = {k: tuple(v) for k, v in data.items()}  # type: ignore
            except Exception:
                self._prev = {}

    def capture_and_diff(self) -> str:
        """
        Walk the project tree, compare to stored snapshot.
        Returns a pseudo-unified diff string.
        Updates the stored snapshot.
        """
        current = self._walk()
        pseudo_diff = self._build_diff(current)
        self._prev = current
        self._snapshot_file.write_text(
            json.dumps({k: list(v) for k, v in current.items()}, indent=2)
        )
        return pseudo_diff

    def _walk(self) -> dict[str, tuple[float, int]]:
        result: dict[str, tuple[float, int]] = {}
        for dirpath, dirnames, filenames in os.walk(self._root):
            # Prune ignored dirs in-place
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
            for fname in filenames:
                if any(fname.endswith(ext) for ext in IGNORE_EXTENSIONS):
                    continue
                fpath = Path(dirpath) / fname
                rel = str(fpath.relative_to(self._root))
                try:
                    stat = fpath.stat()
                    result[rel] = (stat.st_mtime, stat.st_size)
                except OSError:
                    pass
        return result

    def _build_diff(self, current: dict[str, tuple[float, int]]) -> str:
        lines: list[str] = []
        prev_keys = set(self._prev)
        curr_keys = set(current)

        added = curr_keys - prev_keys
        deleted = prev_keys - curr_keys
        modified = {
            k for k in prev_keys & curr_keys
            if self._prev[k] != current[k]
        }

        for path in sorted(added):
            lines.append(f"diff --git a/{path} b/{path}")
            lines.append("new file mode 100644")
            lines.append(f"--- /dev/null")
            lines.append(f"+++ b/{path}")
            lines.append("@@ -0,0 +1,1 @@")
            lines.append("+<new file>")

        for path in sorted(deleted):
            lines.append(f"diff --git a/{path} b/{path}")
            lines.append("deleted file mode 100644")
            lines.append(f"--- a/{path}")
            lines.append("+++ /dev/null")
            lines.append("@@ -1,1 +0,0 @@")
            lines.append("-<deleted file>")

        for path in sorted(modified):
            lines.append(f"diff --git a/{path} b/{path}")
            lines.append(f"--- a/{path}")
            lines.append(f"+++ b/{path}")
            lines.append("@@ -1,1 +1,1 @@")
            lines.append("-<previous>")
            lines.append("+<modified>")

        return "\n".join(lines)
