"""DiffPanel — scrollable, animated diff history."""
from __future__ import annotations

import asyncio

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.containers import ScrollableContainer
from textual.widgets import Static

from codepulse.config import DIFF_ANIMATION_DELAY
from codepulse.git.parser import DiffSnapshot
from codepulse.widgets.diff_entry import DiffEntry


class DiffPanel(Widget):
    DEFAULT_CSS = """
    DiffPanel {
        border: solid $surface;
        height: 100%;
    }
    DiffPanel > #diff-header {
        background: $surface;
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    DiffPanel > ScrollableContainer {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("  Diff History", id="diff-header")
        yield ScrollableContainer(id="diff-scroll")

    def on_mount(self) -> None:
        self._scroll = self.query_one("#diff-scroll", ScrollableContainer)
        self._turn_count = 0

    async def animate_snapshot(self, snapshot: DiffSnapshot) -> None:
        """Mount DiffEntry widgets with staggered animation."""
        if not snapshot.files:
            return

        self._turn_count += 1

        # Turn separator
        header = Static(
            Text.from_markup(
                f" [dim]── Turn {snapshot.turn_index}  "
                f"+{snapshot.total_added}/-{snapshot.total_removed} ──[/dim]"
            ),
            classes="diff-turn-header",
        )
        await self._scroll.mount(header)

        for file_diff in snapshot.files:
            entry = DiffEntry(file_diff)
            await self._scroll.mount(entry)
            self._scroll.scroll_end(animate=False)
            await asyncio.sleep(DIFF_ANIMATION_DELAY)

    def clear_history(self) -> None:
        self._scroll.remove_children()
        self._turn_count = 0
