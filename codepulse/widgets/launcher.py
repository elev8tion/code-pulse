"""LauncherApp — project picker shown when codepulse is run with no arguments."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Input, Label, ListItem, ListView, Static

from codepulse.config import CLONES_DIR
from codepulse.session.manager import SessionManager


# Result tuple: (project_path, project_name, resume)
LaunchResult = tuple[str, str, bool]


def _repo_name(url: str) -> str:
    """Extract repo name from a GitHub URL."""
    url = url.strip().rstrip("/").removesuffix(".git")
    return url.split("/")[-1] or "repo"


def _is_github_url(text: str) -> bool:
    return bool(re.match(r"https?://github\.com/.+/.+|git@github\.com:.+/.+", text.strip()))


class ProjectRow(ListItem):
    """A row in the recent-projects list."""

    def __init__(self, name: str, sessions: int, latest: str, path: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._name = name
        self._sessions = sessions
        self._latest = latest
        self._path = path

    def compose(self) -> ComposeResult:
        text = Text()
        text.append(f" {self._name:<28}", style="bold white")
        text.append(f"{self._sessions:>3} session{'s' if self._sessions != 1 else ' '} ", style="dim")
        text.append(f" {self._latest}", style="cyan")
        yield Static(text)


class LauncherApp(App[Optional[LaunchResult]]):
    """Full-screen project launcher — returns (path, name, resume) or None."""

    CSS = """
    Screen {
        background: #0d0d1a;
        align: center middle;
    }

    #launcher-box {
        width: 70;
        height: auto;
        border: solid $primary;
        background: #0d0d1a;
        padding: 1 2;
    }

    #launcher-title {
        height: 1;
        text-align: center;
        color: $primary;
        margin-bottom: 1;
    }

    #section-label {
        height: 1;
        color: $text-muted;
        margin-bottom: 0;
    }

    #project-list {
        height: auto;
        max-height: 12;
        border: solid $surface;
        margin-bottom: 1;
    }

    #project-list > ListItem {
        padding: 0;
        height: 1;
    }

    #project-list > ListItem.--highlight {
        background: $primary-darken-2;
    }

    #divider {
        height: 1;
        color: $text-muted;
        margin: 1 0;
    }

    .input-row {
        height: 3;
        margin-bottom: 1;
        layout: horizontal;
    }

    .input-label {
        width: 18;
        height: 3;
        content-align: left middle;
        color: $text-muted;
    }

    .input-label.github {
        color: cyan;
    }

    .input-label.local {
        color: green;
    }

    .input-row Input {
        width: 1fr;
        height: 3;
        border: solid $surface;
        background: #1a1a2e;
    }

    .input-row Input:focus {
        border: solid $primary;
        background: #1a1a33;
    }

    #status-line {
        height: 1;
        color: $text-muted;
        margin-top: 1;
        text-align: center;
    }

    #status-line.--error {
        color: red;
    }

    #status-line.--ok {
        color: green;
    }
    """

    BINDINGS = [
        Binding("enter",  "open_selected",  "Open",   priority=True),
        Binding("r",      "resume_selected","Resume"),
        Binding("ctrl+q", "quit_app",       "Quit",   priority=True),
        Binding("escape", "quit_app",       "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._projects = SessionManager.list_projects()

    def compose(self) -> ComposeResult:
        with Vertical(id="launcher-box"):
            yield Static("⚡ CodePulse", id="launcher-title")

            if self._projects:
                yield Static("Recent projects", id="section-label")
                with ListView(id="project-list"):
                    for p in self._projects:
                        yield ProjectRow(
                            name=p["name"],
                            sessions=p["session_count"],
                            latest=p["latest"],
                            path=p.get("path", ""),
                        )
            else:
                yield Static("No saved projects yet.", id="section-label")

            yield Static("─" * 62, id="divider")

            with Horizontal(classes="input-row"):
                yield Label("  Local path", classes="input-label local")
                yield Input(placeholder="/path/to/project  or  ~/my-project", id="path-input")

            with Horizontal(classes="input-row"):
                yield Label("  GitHub URL", classes="input-label github")
                yield Input(placeholder="https://github.com/user/repo", id="github-input")

            yield Static(
                "[dim]↑↓[/dim] select  [dim]Enter[/dim] open  [dim]R[/dim] resume  [dim]Ctrl+Q[/dim] quit",
                id="status-line",
            )
        yield Footer()

    def _set_status(self, msg: str, style: str = "") -> None:
        s = self.query_one("#status-line", Static)
        s.update(msg)
        s.remove_class("--error", "--ok")
        if style:
            s.add_class(style)

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_open_selected(self) -> None:
        """Open from whichever input has focus, or the selected list item."""
        # Check github input first
        gi = self.query_one("#github-input", Input)
        if gi.value.strip():
            self._handle_github(gi.value.strip())
            return

        # Check local path input
        pi = self.query_one("#path-input", Input)
        if pi.value.strip():
            self._handle_local_path(pi.value.strip())
            return

        # Fall back to selected project in list
        self._open_selected_project(resume=False)

    def action_resume_selected(self) -> None:
        self._open_selected_project(resume=True)

    def action_quit_app(self) -> None:
        self.exit(None)

    # ── Input submit handlers ────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "github-input" and event.value.strip():
            self._handle_github(event.value.strip())
        elif event.input.id == "path-input" and event.value.strip():
            self._handle_local_path(event.value.strip())

    # ── Logic ────────────────────────────────────────────────────────────────

    def _open_selected_project(self, resume: bool) -> None:
        lv = self.query_one("#project-list", ListView)
        if lv.highlighted_child is None:
            self._set_status("No project selected.", "--error")
            return
        idx = lv.index
        if idx is None or idx >= len(self._projects):
            return
        p = self._projects[idx]
        # Resolve the actual path from saved session
        from codepulse.session.manager import SessionManager
        session = SessionManager.load_latest(p["name"])
        path = session.project_path if session else str(Path.home())
        self.exit((path, p["name"], resume))

    def _handle_local_path(self, raw: str) -> None:
        path = Path(raw.replace("~", str(Path.home()))).expanduser().resolve()
        if not path.exists():
            self._set_status(f"Path not found: {path}", "--error")
            return
        if not path.is_dir():
            self._set_status(f"Not a directory: {path}", "--error")
            return
        self.exit((str(path), path.name, False))

    def _handle_github(self, url: str) -> None:
        if not _is_github_url(url):
            self._set_status("Doesn't look like a GitHub URL.", "--error")
            return

        repo_name = _repo_name(url)
        dest = CLONES_DIR / repo_name

        if dest.exists():
            self._set_status(f"Already cloned → opening {dest.name}", "--ok")
            self.exit((str(dest), repo_name, False))
            return

        self._set_status(f"Cloning {repo_name}…", "")
        self._clone_and_open(url, dest, repo_name)

    def _clone_and_open(self, url: str, dest: Path, name: str) -> None:
        CLONES_DIR.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(
                ["git", "clone", url, str(dest)],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                err = result.stderr.strip().splitlines()[-1] if result.stderr else "unknown error"
                self._set_status(f"Clone failed: {err}", "--error")
                return
            self.exit((str(dest), name, False))
        except subprocess.TimeoutExpired:
            self._set_status("Clone timed out (120s).", "--error")
        except FileNotFoundError:
            self._set_status("git not found — is git installed?", "--error")
