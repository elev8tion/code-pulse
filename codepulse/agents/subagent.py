"""SubAgent — passive tracker with state machine."""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator, Optional

if TYPE_CHECKING:
    from codepulse.api.claude_client import DispatchClient
    from codepulse.git.parser import DiffSnapshot
    from codepulse.heatmap.aggregator import HeatMapAggregator


class AgentState(Enum):
    SLEEPING = "sleeping"
    PROCESSING = "processing"
    DISCUSSING = "discussing"


SYNOPSIS_PROMPT_TEMPLATE = """\
You are a brief code-change tracker. Given the diff below, produce a concise 3-bullet handoff note (max 150 words total):
• What files changed and what kind of changes
• Inferred reason / intent of the changes
• What the next reviewer should watch for

Be concrete, not vague. Use file names. No preamble.

Files changed: {file_summary}

Diff (truncated):
```
{diff_text}
```
{prev_context}
"""


class SubAgent:
    def __init__(self, slot_id: int, context_window_size: int = 6) -> None:
        self.slot_id = slot_id
        self._context_window_size = context_window_size
        self._state = AgentState.SLEEPING
        self._synopsis: str = ""
        # Discussion continuity: Claude session ID for the ongoing /discuss conversation
        self._discussion_session_id: Optional[str] = None

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def synopsis(self) -> str:
        return self._synopsis

    @property
    def is_sleeping(self) -> bool:
        return self._state == AgentState.SLEEPING

    def receive_handoff(self, synopsis: str) -> None:
        """Accept synopsis from previous agent and clear any prior discussion."""
        self._synopsis = synopsis
        self._discussion_session_id = None

    async def run_post_completion(
        self,
        diff_text: str,
        diff_snapshot: "DiffSnapshot",
        aggregator: "HeatMapAggregator",
        dispatch_client: "DispatchClient",
        heatmaps_dir: Path,
        diffs_dir: Path,
        turn_index: int,
        project_cwd: Optional[str] = None,
    ) -> str:
        """
        Post-completion passive task — triggered explicitly after each completion.
        Ingests diff, updates heatmap, generates synopsis, returns synopsis string.
        """
        self._state = AgentState.PROCESSING

        aggregator.ingest(diff_snapshot)
        aggregator.normalize()
        await aggregator.save(turn_index, heatmaps_dir)

        if diff_text.strip():
            prompt = self._build_synopsis_prompt(diff_text, diff_snapshot)
            synopsis = await dispatch_client.one_shot(
                prompt=prompt,
                use_synopsis_model=True,
            )
        else:
            synopsis = (
                "• No file changes detected in this turn.\n"
                "• Working tree unchanged.\n"
                "• Nothing specific to watch."
            )

        self._synopsis = synopsis
        self._state = AgentState.SLEEPING
        return synopsis

    async def discuss(
        self,
        user_message: str,
        dispatch_client: "DispatchClient",
        project_cwd: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Stream a discussion reply.
        First call seeds the session with context; subsequent calls resume it.
        """
        self._state = AgentState.DISCUSSING

        if self._discussion_session_id is None:
            # First message: embed the synopsis as context in the prompt
            full_prompt = self._build_first_discuss_prompt(user_message)
        else:
            # Subsequent messages: just send the user message, --resume carries context
            full_prompt = user_message

        async for chunk in dispatch_client.stream_one_shot(
            prompt=full_prompt,
            session_id=self._discussion_session_id,
            cwd=project_cwd,
        ):
            yield chunk

        # Capture the discussion session ID for continuity
        if dispatch_client.last_session_id:
            self._discussion_session_id = dispatch_client.last_session_id

        self._state = AgentState.SLEEPING

    def reset_discussion(self) -> None:
        """Clear discussion session — called when /discuss is closed."""
        self._discussion_session_id = None

    def _build_first_discuss_prompt(self, user_message: str) -> str:
        context = (
            f"Context from recent code changes:\n{self._synopsis}\n\n"
            if self._synopsis
            else "No recent changes tracked yet.\n\n"
        )
        return (
            f"You are a code-change analyst. {context}"
            f"The developer asks: {user_message}"
        )

    def _build_synopsis_prompt(self, diff_text: str, snapshot: "DiffSnapshot") -> str:
        file_summary = ", ".join(
            f"{f.path} ({f.change_type}, +{f.lines_added}/-{f.lines_removed})"
            for f in snapshot.files[:10]
        )
        if len(snapshot.files) > 10:
            file_summary += f" … and {len(snapshot.files) - 10} more"

        prev_context = (
            f"\nPrevious context:\n{self._synopsis}"
            if self._synopsis
            else ""
        )

        return SYNOPSIS_PROMPT_TEMPLATE.format(
            file_summary=file_summary,
            diff_text=diff_text[:3000],
            prev_context=prev_context,
        )
