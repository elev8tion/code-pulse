"""ProcessManager — cards for running/monitoring dev processes."""
from __future__ import annotations

from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, RichLog, Static

from codepulse.process.models import ProcessRecord, ProcessStatus


STATUS_DOT = {
    ProcessStatus.RUNNING: ("[bold green]●[/]", "--running"),
    ProcessStatus.ERROR:   ("[bold red]●[/]",   "--error"),
    ProcessStatus.STOPPED: ("[dim]○[/]",         ""),
}


class ProcessCard(Widget):
    """Card showing one process — collapsed (4 rows) or expanded (12 rows)."""

    DEFAULT_CSS = """
    ProcessCard {
        height: 5;
        border: solid $surface;
        padding: 0 1;
        margin: 0 0 1 0;
        layout: vertical;
        transition: border 200ms linear;
    }
    ProcessCard.--running { border: solid #00cc44; }
    ProcessCard.--error   { border: solid #ff4444; }
    ProcessCard.--expanded { height: 14; }
    ProcessCard > #proc-header {
        layout: horizontal;
        height: 3;
        align: left middle;
    }
    ProcessCard > #proc-header > #proc-dot   { width: 3; height: 1; }
    ProcessCard > #proc-header > #proc-name  { width: 1fr; height: 1; }
    ProcessCard > #proc-header > #proc-btn   { width: 8; height: 3; }
    ProcessCard > #last-line-bar {
        height: 1;
        color: $text-muted;
        overflow: hidden;
    }
    ProcessCard > #proc-output {
        display: none;
        height: 1fr;
        border-top: solid $surface;
    }
    ProcessCard.--expanded > #proc-output { display: block; }
    """

    expanded: reactive[bool] = reactive(False)

    class ToggleRequested(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    def __init__(self, record: ProcessRecord, **kwargs) -> None:
        super().__init__(**kwargs)
        self._record = record

    def compose(self) -> ComposeResult:
        with Horizontal(id="proc-header"):
            yield Static("○", id="proc-dot")
            yield Static(self._record.name, id="proc-name")
            yield Button("Run", id="proc-btn", variant="success")
        yield Static("", id="last-line-bar")
        with ScrollableContainer(id="proc-output"):
            yield RichLog(id=f"log-{self._record.name}", wrap=True, highlight=False, markup=False)

    def on_mount(self) -> None:
        self._update_status_display(self._record.status)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.post_message(self.ToggleRequested(self._record.name))

    def on_click(self) -> None:
        self.expanded = not self.expanded

    def watch_expanded(self, val: bool) -> None:
        self.set_class(val, "--expanded")

    def update_status(self, status: ProcessStatus) -> None:
        self._record.status = status
        self._update_status_display(status)

    def _update_status_display(self, status: ProcessStatus) -> None:
        dot_markup, css_class = STATUS_DOT[status]
        try:
            dot = self.query_one("#proc-dot", Static)
            dot.update(dot_markup)
            btn = self.query_one("#proc-btn", Button)
            if status == ProcessStatus.RUNNING:
                btn.label = "Stop"
                btn.variant = "error"
            else:
                btn.label = "Run"
                btn.variant = "success"
        except Exception:
            pass

        self.remove_class("--running", "--error")
        if css_class:
            self.add_class(css_class)

    def append_output(self, line: str) -> None:
        try:
            log = self.query_one(f"#log-{self._record.name}", RichLog)
            log.write(line)
            last = self.query_one("#last-line-bar", Static)
            truncated = line[:55] + "…" if len(line) > 55 else line
            last.update(f"[dim]{truncated}[/dim]")
        except Exception:
            pass


class ProcessManager(Widget):
    """Manages all process cards and runners."""

    DEFAULT_CSS = """
    ProcessManager {
        height: 100%;
        layout: vertical;
        overflow-y: auto;
        padding: 0 1;
    }
    ProcessManager > #proc-list {
        height: 1fr;
        overflow-y: auto;
        layout: vertical;
    }
    ProcessManager > #proc-empty {
        height: 3;
        content-align: center middle;
        color: $text-muted;
    }
    """

    class OutputReceived(Message):
        def __init__(self, name: str, line: str) -> None:
            super().__init__()
            self.name = name
            self.line = line

    class StatusChanged(Message):
        def __init__(self, name: str, status: ProcessStatus) -> None:
            super().__init__()
            self.name = name
            self.status = status

    def compose(self) -> ComposeResult:
        yield Static("[dim]No processes detected. Open a project to auto-detect.[/dim]", id="proc-empty")
        yield ScrollableContainer(id="proc-list")

    def on_process_manager_output_received(self, event: "ProcessManager.OutputReceived") -> None:
        try:
            card = self.query_one(f"#pcard-{event.name}", ProcessCard)
            card.append_output(event.line)
        except Exception:
            pass

    def on_process_manager_status_changed(self, event: "ProcessManager.StatusChanged") -> None:
        try:
            card = self.query_one(f"#pcard-{event.name}", ProcessCard)
            card.update_status(event.status)
        except Exception:
            pass

    async def load_processes(self, records: list[ProcessRecord]) -> None:
        """Mount process cards from detected records."""
        proc_list = self.query_one("#proc-list", ScrollableContainer)
        empty = self.query_one("#proc-empty", Static)

        await proc_list.remove_children()

        if not records:
            empty.display = True
            return

        empty.display = False
        for record in records:
            card = ProcessCard(record, id=f"pcard-{record.name}")
            await proc_list.mount(card)

    def output_callback(self, name: str, line: str) -> None:
        """Called from ProcessRunner — thread-safe via post_message."""
        self.post_message(self.OutputReceived(name, line))

    def status_callback(self, name: str, status: ProcessStatus) -> None:
        """Called from ProcessRunner — thread-safe via post_message."""
        self.post_message(self.StatusChanged(name, status))
