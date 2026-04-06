"""ToolPalette — visual cards for every Claude tool, glows when used."""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget


# All Claude Code tools with icons and descriptions
TOOLS: list[tuple[str, str, str]] = [
    ("Bash",      "⚡", "Run commands"),
    ("Read",      "📖", "Read files"),
    ("Write",     "✏️",  "Create files"),
    ("Edit",      "🔄", "Modify files"),
    ("Glob",      "🔍", "Find files"),
    ("Grep",      "🔎", "Search code"),
    ("WebFetch",  "🌐", "Fetch URL"),
    ("WebSearch", "🔭", "Search web"),
    ("Agent",     "🤖", "Spawn agent"),
    ("Task",      "📋", "Manage tasks"),
    ("TodoWrite", "✅", "Write todos"),
]


class ToolCard(Widget):
    """Single tool card — animates when Claude uses the tool."""

    DEFAULT_CSS = """
    ToolCard {
        width: 11;
        height: 6;
        border: solid $surface;
        background: #0d0d1a;
        content-align: center middle;
        text-align: center;
        padding: 0 1;
        margin: 0 1;
        transition: background 150ms linear, border 150ms linear;
    }
    ToolCard:hover {
        border: solid $primary;
        background: #1a1a2e;
    }
    ToolCard.--glow {
        background: #0d2a1a;
        border: solid #00ff41;
    }
    """

    is_active: reactive[bool] = reactive(False)

    def __init__(self, name: str, icon: str, desc: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._name = name
        self._icon = icon
        self._desc = desc

    def watch_is_active(self, active: bool) -> None:
        if active:
            self.add_class("--glow")
            self.set_timer(1.2, self._clear_glow)

    def _clear_glow(self) -> None:
        self.remove_class("--glow")
        self.is_active = False

    def on_click(self) -> None:
        self.post_message(ToolPalette.ToolHinted(self._name))

    def render(self) -> Text:
        text = Text(justify="center")
        color = "#00ff41" if "--glow" in self.classes else "#336655"
        text.append(f"{self._icon}\n", style=color)
        text.append(self._name, style="bold white")
        text.append(f"\n{self._desc}", style="dim")
        return text


class ToolPalette(Widget):
    """Horizontal strip of tool cards."""

    DEFAULT_CSS = """
    ToolPalette {
        height: 100%;
        layout: vertical;
        overflow-y: hidden;
    }
    ToolPalette > #tool-header {
        height: 1;
        padding: 0 1;
        color: $text-muted;
        background: $surface;
    }
    ToolPalette > #tool-row {
        height: 1fr;
        layout: horizontal;
        overflow-x: auto;
        overflow-y: hidden;
        padding: 0 1;
        align: left middle;
    }
    """

    class ToolHinted(Message):
        """Posted when a tool card is clicked — app appends hint to prompt."""
        def __init__(self, tool_name: str) -> None:
            super().__init__()
            self.tool_name = tool_name

    def compose(self) -> ComposeResult:
        yield Widget(id="tool-header")  # placeholder for label — rendered via on_mount
        with Horizontal(id="tool-row"):
            for name, icon, desc in TOOLS:
                yield ToolCard(name, icon, desc, id=f"tool-{name.lower()}")

    def on_mount(self) -> None:
        header = self.query_one("#tool-header")
        header.styles.color = "gray"

    def activate_tool(self, tool_name: str) -> None:
        """Called by app when stream-json emits a tool_call event."""
        # Normalize: "bash" → "Bash", "web_fetch" → "WebFetch", etc.
        normalized = _normalize_tool_name(tool_name)
        try:
            card = self.query_one(f"#tool-{normalized.lower()}", ToolCard)
            card.is_active = True
        except Exception:
            pass  # Unknown tool — ignore gracefully


def _normalize_tool_name(raw: str) -> str:
    """Normalize CLI tool names to match our palette IDs."""
    mapping = {
        "bash": "Bash",
        "read_file": "Read",
        "read": "Read",
        "write_file": "Write",
        "write": "Write",
        "edit_file": "Edit",
        "edit": "Edit",
        "str_replace_editor": "Edit",
        "glob": "Glob",
        "grep": "Grep",
        "web_fetch": "WebFetch",
        "webfetch": "WebFetch",
        "web_search": "WebSearch",
        "websearch": "WebSearch",
        "agent": "Agent",
        "task": "Task",
        "todowrite": "TodoWrite",
        "todo_write": "TodoWrite",
    }
    return mapping.get(raw.lower(), raw)
