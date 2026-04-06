"""DiffEntry — single animated row in the Diff Panel."""
from __future__ import annotations

from rich.text import Text
from textual.widget import Widget

from codepulse.git.parser import FileDiff
from codepulse.utils.colors import change_type_color, change_type_icon


class DiffEntry(Widget):
    DEFAULT_CSS = """
    DiffEntry {
        height: 1;
        padding: 0 1;
        opacity: 0.0;
        transition: opacity 300ms linear;
    }
    DiffEntry.--visible {
        opacity: 1.0;
    }
    """

    def __init__(self, file_diff: FileDiff, **kwargs) -> None:
        super().__init__(**kwargs)
        self._file_diff = file_diff

    def on_mount(self) -> None:
        self.call_after_refresh(self._become_visible)

    def _become_visible(self) -> None:
        self.add_class("--visible")

    def render(self) -> Text:
        fd = self._file_diff
        color = change_type_color(fd.change_type)
        icon = change_type_icon(fd.change_type)

        text = Text()
        text.append(f" {icon} ", style=f"bold {color}")
        text.append(fd.path, style="white")

        # Pad to align the +/- numbers
        padding = max(0, 45 - len(fd.path))
        text.append(" " * padding)

        if fd.lines_added:
            text.append(f"+{fd.lines_added}", style="green")
        if fd.lines_added and fd.lines_removed:
            text.append(" / ", style="dim")
        if fd.lines_removed:
            text.append(f"-{fd.lines_removed}", style="red")

        return text
