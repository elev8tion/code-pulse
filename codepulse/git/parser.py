"""Parse unified diff text into structured DiffSnapshot."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class FileDiff(BaseModel):
    path: str
    change_type: str  # "added" | "modified" | "deleted"
    lines_added: int
    lines_removed: int
    directory: str


class DiffSnapshot(BaseModel):
    turn_index: int
    raw_text: str
    files: list[FileDiff]
    total_added: int
    total_removed: int
    directories_affected: list[str]


class UnifiedDiffParser:
    def parse(self, raw_diff: str, turn_index: int) -> DiffSnapshot:
        if not raw_diff.strip():
            return DiffSnapshot(
                turn_index=turn_index,
                raw_text="",
                files=[],
                total_added=0,
                total_removed=0,
                directories_affected=[],
            )

        try:
            import unidiff
            patch = unidiff.PatchSet(raw_diff)
            files = [self._parse_patched_file(pf) for pf in patch]
        except Exception:
            # Fallback: manual line-counting parser
            files = self._manual_parse(raw_diff)

        total_added = sum(f.lines_added for f in files)
        total_removed = sum(f.lines_removed for f in files)
        dirs = list({f.directory for f in files if f.directory})

        return DiffSnapshot(
            turn_index=turn_index,
            raw_text=raw_diff,
            files=files,
            total_added=total_added,
            total_removed=total_removed,
            directories_affected=dirs,
        )

    def _parse_patched_file(self, pf) -> FileDiff:
        import unidiff
        if pf.is_added_file:
            change_type = "added"
            path = pf.path
        elif pf.is_removed_file:
            change_type = "deleted"
            path = pf.source_file.lstrip("a/")
        else:
            change_type = "modified"
            path = pf.path

        # Strip leading a/ or b/ from unidiff paths
        path = path.lstrip("ab").lstrip("/")

        added = sum(h.added for h in pf)
        removed = sum(h.removed for h in pf)
        directory = str(Path(path).parent) if "/" in path else "."

        return FileDiff(
            path=path,
            change_type=change_type,
            lines_added=added,
            lines_removed=removed,
            directory=directory,
        )

    def _manual_parse(self, raw_diff: str) -> list[FileDiff]:
        """Fallback parser if unidiff is unavailable."""
        files: list[FileDiff] = []
        current_path: str | None = None
        added = removed = 0
        change_type = "modified"

        for line in raw_diff.splitlines():
            if line.startswith("diff --git"):
                if current_path:
                    files.append(self._make_file_diff(current_path, change_type, added, removed))
                current_path = None
                added = removed = 0
                change_type = "modified"
            elif line.startswith("--- ") and current_path is None:
                pass
            elif line.startswith("+++ b/"):
                current_path = line[6:]
            elif line.startswith("new file"):
                change_type = "added"
            elif line.startswith("deleted file"):
                change_type = "deleted"
            elif line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1

        if current_path:
            files.append(self._make_file_diff(current_path, change_type, added, removed))

        return files

    def _make_file_diff(self, path: str, change_type: str, added: int, removed: int) -> FileDiff:
        directory = str(Path(path).parent) if "/" in path else "."
        return FileDiff(
            path=path,
            change_type=change_type,
            lines_added=added,
            lines_removed=removed,
            directory=directory,
        )
