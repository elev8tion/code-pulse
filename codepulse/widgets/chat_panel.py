"""ChatPanel — main conversation display with streaming output."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import RichLog

from codepulse.widgets.prompt_input import PromptInput


class ChatPanel(Widget):
    DEFAULT_CSS = """
    ChatPanel {
        layout: vertical;
        height: 100%;
        border: solid $primary-darken-2;
    }
    ChatPanel > RichLog {
        height: 1fr;
        padding: 0 1;
    }
    """

    streaming: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        yield RichLog(id="chat-log", wrap=True, highlight=True, markup=True)
        yield PromptInput(id="prompt-input")

    def on_mount(self) -> None:
        self._log = self.query_one("#chat-log", RichLog)
        self._prompt = self.query_one("#prompt-input", PromptInput)
        self._log.write(
            "[bold cyan]CodePulse[/] — Claude Code TUI with live codebase visualization\n"
            "Type your prompt and press Enter. Use [bold]/help[/] for commands.\n"
            "─" * 50
        )

    def write_user(self, text: str) -> None:
        self._log.write(f"\n[bold green]You:[/] {text}")

    def begin_assistant_turn(self) -> None:
        self.streaming = True
        self._log.write("\n[bold cyan]Claude:[/] ", end="")
        self._prompt.disable()

    def stream_chunk(self, chunk: str) -> None:
        self._log.write(chunk, end="")

    def end_assistant_turn(self) -> None:
        self.streaming = False
        self._log.write("")  # newline after stream
        self._log.write("─" * 50)
        self._prompt.enable()

    def write_system(self, text: str, style: str = "dim") -> None:
        self._log.write(f"[{style}]{text}[/{style}]")

    def write_discuss_open(self, agent_slot: int, preview: str) -> None:
        self._log.write(
            f"\n[bold yellow]── Discussion Mode (Agent {agent_slot + 1}/3) ──[/]\n"
            f"[dim]{preview}[/dim]"
        )
        self._prompt.set_discuss_mode(True)

    def write_discuss_close(self) -> None:
        self._log.write("[bold yellow]── Normal Mode ──[/]\n")
        self._prompt.set_discuss_mode(False)

    def begin_agent_turn(self, agent_slot: int) -> None:
        self._log.write(f"\n[bold yellow]Agent {agent_slot + 1}:[/] ", end="")

    def write_help(self) -> None:
        self._log.write(
            "\n[bold]Commands:[/]\n"
            "  [cyan]/discuss[/]  — open discussion with the current subagent\n"
            "  [cyan]/discuss[/]  — (again) exit discussion mode\n"
            "  [cyan]/agents[/]   — show subagent pool status\n"
            "  [cyan]/clear[/]    — clear the chat log\n"
            "  [cyan]/export[/]   — export session to markdown\n"
            "  [cyan]/new[/]      — start a new session\n"
            "  [cyan]/help[/]     — show this message\n"
            "  [bold]Ctrl+Q[/]    — quit CodePulse\n"
        )

    def clear_log(self) -> None:
        self._log.clear()

    def disable_input(self) -> None:
        self._prompt.disable()

    def enable_input(self) -> None:
        self._prompt.enable()
