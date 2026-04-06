"""PromptInput — user input widget with slash command parsing."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input


COMMANDS = {
    "/discuss", "/exit", "/new", "/export", "/agents", "/help", "/clear",
    "/tools", "/processes", "/actions", "/pin",
}


class PromptInput(Widget):
    DEFAULT_CSS = """
    PromptInput {
        height: 3;
        border-top: solid $surface;
        padding: 0 1;
    }
    PromptInput Input {
        border: none;
        height: 1;
        margin-top: 1;
        background: transparent;
    }
    """

    class Submitted(Message):
        def __init__(self, text: str, is_command: bool, command: str | None, args: str) -> None:
            super().__init__()
            self.text = text
            self.is_command = is_command
            self.command = command
            self.args = args

    def compose(self) -> ComposeResult:
        yield Input(placeholder="> Ask Claude... (type /help for commands)", id="main-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.clear()

        is_command, command, args = self._parse(text)
        self.post_message(self.Submitted(text=text, is_command=is_command, command=command, args=args))

    def _parse(self, text: str) -> tuple[bool, str | None, str]:
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            if cmd in COMMANDS:
                return True, cmd, args
        return False, None, text

    def disable(self) -> None:
        inp = self.query_one("#main-input", Input)
        inp.disabled = True
        inp.placeholder = "Claude is thinking..."

    def enable(self) -> None:
        inp = self.query_one("#main-input", Input)
        inp.disabled = False
        inp.placeholder = "> Ask Claude... (type /help for commands)"
        inp.focus()

    def set_discuss_mode(self, active: bool) -> None:
        inp = self.query_one("#main-input", Input)
        if active:
            inp.placeholder = "> Discuss with agent... (/discuss to exit)"
        else:
            inp.placeholder = "> Ask Claude... (type /help for commands)"
