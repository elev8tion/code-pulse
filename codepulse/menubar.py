"""CodePulse menu bar app — lives in the macOS menu bar, spawns the TUI."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import rumps

# Absolute paths (works from LaunchAgent with no PATH)
_HERE = Path(__file__).parent.parent.resolve()
VENV_PYTHON  = _HERE / ".venv/bin/python"
CODEPULSE    = _HERE / ".venv/bin/codepulse"
PID_FILE     = Path.home() / ".codepulse" / "running.pid"
TERMINAL_APP = "/System/Applications/Utilities/Terminal.app"


def _is_running() -> bool:
    """True if a CodePulse TUI is live (checked via PID file)."""
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)   # signal 0 = existence check only
        return True
    except (ValueError, OSError):
        PID_FILE.unlink(missing_ok=True)
        return False


def _open_terminal(cmd: str) -> None:
    """Open a new Terminal.app window running cmd."""
    escaped = cmd.replace('"', '\\"')
    script = (
        f'tell application "Terminal"\n'
        f'    activate\n'
        f'    do script "{escaped}"\n'
        f'end tell'
    )
    subprocess.Popen(["osascript", "-e", script])


def _bring_terminal_to_front() -> None:
    subprocess.Popen(["osascript", "-e", 'tell application "Terminal" to activate'])


class CodePulseBar(rumps.App):
    def __init__(self) -> None:
        super().__init__("⚡", quit_button=None)
        self._build_menu()

        # Poll every 3 s to update running indicator
        rumps.Timer(self._poll, 3).start()

    # ── Menu construction ────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        self.menu.clear()

        running = _is_running()
        if running:
            toggle = rumps.MenuItem("● Running  —  click to focus", callback=self._focus)
        else:
            toggle = rumps.MenuItem("Open CodePulse", callback=self._open_launcher)

        self._toggle_item = toggle
        self.menu.add(toggle)
        self.menu.add(rumps.separator)

        # Recent projects (up to 6)
        try:
            from codepulse.session.manager import SessionManager
            projects = SessionManager.list_projects()[:6]
            if projects:
                for p in projects:
                    item = rumps.MenuItem(
                        f"  {p['name']}",
                        callback=self._make_project_opener(p["name"]),
                    )
                    self.menu.add(item)
                self.menu.add(rumps.separator)
        except Exception:
            pass

        self.menu.add(rumps.MenuItem("Clone GitHub Repo…", callback=self._clone_repo))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit Menu Bar", callback=self._quit))

    def _poll(self, _: rumps.Timer) -> None:
        running = _is_running()
        if running:
            self._toggle_item.title = "● Running  —  click to focus"
            self._toggle_item.set_callback(self._focus)
        else:
            self._toggle_item.title = "Open CodePulse"
            self._toggle_item.set_callback(self._open_launcher)

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _open_launcher(self, _=None) -> None:
        _open_terminal(str(CODEPULSE))

    def _focus(self, _=None) -> None:
        _bring_terminal_to_front()

    def _make_project_opener(self, name: str):
        def _open(_=None):
            _open_terminal(f'{CODEPULSE} resume {name}')
        return _open

    def _clone_repo(self, _=None) -> None:
        response = rumps.Window(
            message="Paste a GitHub URL to clone and open:",
            title="Clone GitHub Repo",
            default_text="https://github.com/user/repo",
            ok="Clone",
            cancel="Cancel",
            dimensions=(400, 24),
        ).run()

        if response.clicked and response.text.strip():
            url = response.text.strip()
            repo_name = url.rstrip("/").removesuffix(".git").split("/")[-1]
            from codepulse.config import CLONES_DIR
            dest = CLONES_DIR / repo_name
            if dest.exists():
                _open_terminal(f'{CODEPULSE} open "{dest}"')
                return
            # Clone then open
            CLONES_DIR.mkdir(parents=True, exist_ok=True)
            clone_cmd = f'git clone "{url}" "{dest}" && {CODEPULSE} open "{dest}"'
            _open_terminal(clone_cmd)

    def _quit(self, _=None) -> None:
        rumps.quit_application()


def main() -> None:
    rumps.debug_mode(False)
    CodePulseBar().run()


if __name__ == "__main__":
    main()
