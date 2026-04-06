"""QuickActionDeck — one-click prompt cards for solo dev workflows."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget

from codepulse.config import ACTIONS_FILE


class StackHints(BaseModel):
    cloudflare: str = "Deploy this project to Cloudflare Pages using wrangler deploy"
    ncb: str = "Deploy the NoCodeBackend configuration and sync the schema"
    flutter: str = "Build the Flutter app for release"
    default: str = "Deploy this project. Detect the deployment method from the project files."


class ActionDefinition(BaseModel):
    id: str
    label: str
    icon: str = ""
    prompt: Optional[str] = None
    needs_sub_prompt: bool = False
    sub_prompt_label: str = "Enter details:"
    stack_aware: bool = False
    stack_hints: StackHints = Field(default_factory=StackHints)
    color: str = "white"


DEFAULT_ACTIONS: list[ActionDefinition] = [
    ActionDefinition(id="fix-bugs",        label="Fix Bugs",        icon="🔧", prompt="Look at any errors and fix them", color="red"),
    ActionDefinition(id="write-tests",     label="Write Tests",     icon="🧪", prompt="Write tests for the changes made in the last turn", color="yellow"),
    ActionDefinition(id="explain-this",    label="Explain This",    icon="💡", prompt="Explain what the current state of this codebase does at a high level", color="cyan"),
    ActionDefinition(id="review-diff",     label="Review Diff",     icon="🔍", prompt="Review my recent changes and suggest improvements", color="blue"),
    ActionDefinition(id="scaffold",        label="Scaffold",        icon="🏗",  prompt="Scaffold a new feature: ", needs_sub_prompt=True, sub_prompt_label="What feature?", color="magenta"),
    ActionDefinition(id="deploy",          label="Deploy",          icon="🚀", stack_aware=True, color="green"),
    ActionDefinition(id="whats-next",      label="What's Next",     icon="🗺",  prompt="Based on the current state, what should I work on next?", color="white"),
    ActionDefinition(id="commit-push",     label="Commit & Push",   icon="📦", prompt="Stage all changes, write a good commit message, and commit", color="green"),
    ActionDefinition(id="clean-up",        label="Clean Up",        icon="🧹", prompt="Refactor and clean up any messy code from the recent changes", color="yellow"),
    ActionDefinition(id="add-feature",     label="Add Feature",     icon="✨", prompt="Add a new feature: ", needs_sub_prompt=True, sub_prompt_label="Describe the feature:", color="cyan"),
    ActionDefinition(id="debug",           label="Debug",           icon="🐛", prompt="Help me debug what's going wrong. Start by reading the relevant files and errors.", color="red"),
    ActionDefinition(id="docs",            label="Write Docs",      icon="📝", prompt="Write clear documentation for the recent changes", color="dim"),
]

COLOR_MAP = {
    "red":     "#ff4444",
    "yellow":  "#ffaa00",
    "cyan":    "#00ccff",
    "blue":    "#4488ff",
    "magenta": "#cc44ff",
    "green":   "#00cc44",
    "white":   "#cccccc",
    "dim":     "#666666",
}


class ActionCard(Widget):
    """Single clickable prompt card."""

    DEFAULT_CSS = """
    ActionCard {
        width: 14;
        height: 6;
        border: solid $surface;
        background: #0d0d1a;
        content-align: center middle;
        text-align: center;
        padding: 0 1;
        margin: 0 1;
        transition: background 120ms linear, border 120ms linear;
    }
    ActionCard:hover {
        background: #1a1a2e;
        border: solid $accent;
    }
    ActionCard.--fired {
        background: #1a2a1a;
        border: solid #00ff41;
    }
    """

    class Fired(Message):
        def __init__(
            self,
            action_id: str,
            prompt: str,
            label: str,
            needs_sub_prompt: bool = False,
            sub_prompt_label: str = "Enter details:",
        ) -> None:
            super().__init__()
            self.action_id = action_id
            self.prompt = prompt
            self.label = label
            self.needs_sub_prompt = needs_sub_prompt
            self.sub_prompt_label = sub_prompt_label

    def __init__(self, action: ActionDefinition, cwd: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._action = action
        self._cwd = cwd

    def on_click(self) -> None:
        prompt = self._resolve_prompt()
        self.add_class("--fired")
        self.set_timer(0.8, lambda: self.remove_class("--fired"))
        self.post_message(ActionCard.Fired(
            action_id=self._action.id,
            prompt=prompt,
            label=self._action.label,
            needs_sub_prompt=self._action.needs_sub_prompt,
            sub_prompt_label=self._action.sub_prompt_label,
        ))

    def _resolve_prompt(self) -> str:
        if self._action.stack_aware:
            return self._resolve_deploy()
        return self._action.prompt or ""

    def _resolve_deploy(self) -> str:
        root = Path(self._cwd) if self._cwd else Path.cwd()
        hints = self._action.stack_hints
        if (root / "wrangler.toml").exists() or (root / "wrangler.jsonc").exists():
            return hints.cloudflare
        if (root / ".ncb").exists() or (root / "ncb.config.json").exists():
            return hints.ncb
        if (root / "pubspec.yaml").exists():
            return hints.flutter
        return hints.default

    def render(self) -> Text:
        action = self._action
        color = COLOR_MAP.get(action.color, "#cccccc")
        glow = "--fired" in self.classes

        text = Text(justify="center")
        text.append(f"{action.icon}\n", style=color if not glow else "#00ff41")
        text.append(action.label, style=f"bold {'#00ff41' if glow else 'white'}")
        return text


class QuickActionDeck(Widget):
    """Horizontal scrollable strip of ActionCards."""

    DEFAULT_CSS = """
    QuickActionDeck {
        height: 100%;
        layout: vertical;
        overflow-y: hidden;
    }
    QuickActionDeck > #actions-row {
        height: 1fr;
        layout: horizontal;
        overflow-x: auto;
        overflow-y: hidden;
        padding: 0 1;
        align: left middle;
    }
    """

    def __init__(self, cwd: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._cwd = cwd

    def compose(self) -> ComposeResult:
        actions = _load_actions()
        with Horizontal(id="actions-row"):
            for action in actions:
                yield ActionCard(action, cwd=self._cwd, id=f"action-{action.id}")

    def update_cwd(self, cwd: str) -> None:
        """Update stack-aware cards when project changes."""
        self._cwd = cwd
        for card in self.query(ActionCard):
            card._cwd = cwd


def _load_actions() -> list[ActionDefinition]:
    if ACTIONS_FILE.exists():
        try:
            data = json.loads(ACTIONS_FILE.read_text())
            return [ActionDefinition(**a) for a in data.get("actions", [])]
        except Exception:
            pass
    return DEFAULT_ACTIONS


def write_default_actions() -> None:
    """Write the default actions.json to ~/.codepulse/ if it doesn't exist."""
    if ACTIONS_FILE.exists():
        return
    ACTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "actions": [a.model_dump() for a in DEFAULT_ACTIONS],
    }
    ACTIONS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
