"""BottomDrawer — collapsible tabbed panel for Tools, Processes, Actions."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import TabbedContent, TabPane

from codepulse.widgets.tool_palette import ToolPalette
from codepulse.widgets.process_manager import ProcessManager
from codepulse.widgets.quick_actions import QuickActionDeck

DRAWER_OPEN   = 10
DRAWER_CLOSED = 2


class BottomDrawer(Widget):
    DEFAULT_CSS = """
    BottomDrawer {
        height: 10;
        border-top: solid $primary-darken-2;
        background: #090912;
        transition: height 200ms in_out_cubic;
    }
    BottomDrawer.--collapsed {
        height: 2;
    }
    BottomDrawer TabbedContent {
        height: 100%;
    }
    BottomDrawer TabbedContent > TabPane {
        height: 1fr;
        padding: 0;
    }
    """

    collapsed: reactive[bool] = reactive(False)

    def __init__(self, cwd: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._cwd = cwd

    def compose(self) -> ComposeResult:
        with TabbedContent(id="drawer-tabs"):
            with TabPane("⚡ Tools", id="tab-tools"):
                yield ToolPalette(id="tool-palette")
            with TabPane("⚙ Processes", id="tab-processes"):
                yield ProcessManager(id="process-manager")
            with TabPane("▶ Actions", id="tab-actions"):
                yield QuickActionDeck(cwd=self._cwd, id="quick-actions")

    def watch_collapsed(self, val: bool) -> None:
        self.set_class(val, "--collapsed")

    def toggle(self) -> None:
        self.collapsed = not self.collapsed

    def show_tab(self, tab_id: str) -> None:
        """Expand and switch to a specific tab."""
        self.collapsed = False
        try:
            self.query_one("#drawer-tabs", TabbedContent).active = tab_id
        except Exception:
            pass
