"""StatusBar — bottom bar showing project, session, agent, state, processes, last tool."""
from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget


class StatusBar(Widget):
    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary-darken-3;
        color: $text;
        padding: 0 1;
    }
    """

    project_name: reactive[str]  = reactive("")
    session_date: reactive[str]  = reactive("")
    agent_slot:   reactive[int]  = reactive(0)
    agent_total:  reactive[int]  = reactive(3)
    status:       reactive[str]  = reactive("ready")
    is_git:       reactive[bool] = reactive(True)
    process_count: reactive[int] = reactive(0)
    last_tool:    reactive[str]  = reactive("")

    STATUS_STYLES = {
        "ready":      ("ready",       "green"),
        "streaming":  ("streaming",   "cyan"),
        "processing": ("processing…", "yellow"),
        "discussing": ("discuss",     "magenta"),
        "exporting":  ("exporting",   "blue"),
    }

    def render(self) -> Text:
        text = Text(no_wrap=True, overflow="ellipsis")
        text.append(" CodePulse ", style="bold cyan on #1a1a2e")
        text.append("│", style="dim")
        text.append(f" {self.project_name} ", style="bold")
        text.append("│", style="dim")
        text.append(f" {self.session_date} ")
        text.append("│", style="dim")
        text.append(f" A{self.agent_slot + 1}/{self.agent_total} ", style="yellow")
        text.append("│", style="dim")

        # Running process count
        if self.process_count > 0:
            text.append(f" {self.process_count}p ", style="bold green")
        else:
            text.append(" 0p ", style="dim")
        text.append("│", style="dim")

        # Last tool used (clears after 5s via app timer)
        if self.last_tool:
            text.append(f" {self.last_tool} ", style="bold magenta")
            text.append("│", style="dim")

        vcs = "git" if self.is_git else "snap"
        text.append(f" {vcs} ")
        text.append("│", style="dim")

        label, style = self.STATUS_STYLES.get(self.status, (self.status, "white"))
        text.append(f" {label} ", style=f"bold {style}")

        return text
