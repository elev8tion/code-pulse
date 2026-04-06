"""DiffTracker — captures git diffs or falls back to file snapshots."""
from __future__ import annotations

import asyncio
from pathlib import Path

import aiofiles

from codepulse.git.snapshot import FileSnapshot
from codepulse.utils.paths import snapshot_file as get_snapshot_file


class DiffTracker:
    def __init__(self, project_path: Path, project_name: str) -> None:
        self._root = project_path
        self._project_name = project_name
        self._is_git: bool | None = None
        self._snapshot: FileSnapshot | None = None

    @property
    def is_git_repo(self) -> bool:
        if self._is_git is None:
            self._is_git = (self._root / ".git").exists()
        return self._is_git

    async def initialize(self) -> None:
        """Set up snapshot baseline for non-git projects."""
        if not self.is_git_repo:
            sf = get_snapshot_file(self._project_name)
            self._snapshot = FileSnapshot(self._root, sf)
            self._snapshot.load()

    async def capture_snapshot(self) -> str:
        """
        Return raw unified diff text since the last capture.
        Empty string if no changes.
        """
        if self.is_git_repo:
            return await self._git_diff()
        else:
            assert self._snapshot is not None
            return self._snapshot.capture_and_diff()

    async def _git_diff(self) -> str:
        """Run `git diff HEAD` as a subprocess."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "diff", "HEAD",
                cwd=str(self._root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            diff = stdout.decode("utf-8", errors="replace")
            if not diff.strip():
                # Also check staged changes
                proc2 = await asyncio.create_subprocess_exec(
                    "git", "diff", "--cached",
                    cwd=str(self._root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout2, _ = await asyncio.wait_for(proc2.communicate(), timeout=15.0)
                diff = stdout2.decode("utf-8", errors="replace")
            return diff
        except Exception:
            return ""

    async def save_diff(self, diff_text: str, turn_index: int, diffs_dir: Path) -> Path:
        path = diffs_dir / f"{turn_index:03d}-diff.txt"
        async with aiofiles.open(path, "w") as f:
            await f.write(diff_text)
        return path
