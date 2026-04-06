"""DiscussionSession — manages /discuss mode lifecycle."""
from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator, Optional

if TYPE_CHECKING:
    from codepulse.agents.subagent import SubAgent
    from codepulse.api.claude_client import DispatchClient


class DiscussionSession:
    """Wraps a SubAgent in /discuss mode."""

    def __init__(
        self,
        agent: "SubAgent",
        dispatch_client: "DispatchClient",
        project_cwd: Optional[str] = None,
    ) -> None:
        self._agent = agent
        self._client = dispatch_client
        self._cwd = project_cwd
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def agent_slot(self) -> int:
        return self._agent.slot_id

    def open(self) -> str:
        self._active = True
        synopsis_preview = self._agent.synopsis[:200] if self._agent.synopsis else "No changes tracked yet."
        return synopsis_preview

    def close(self) -> None:
        self._active = False
        self._agent.reset_discussion()

    async def send(self, user_message: str) -> AsyncIterator[str]:
        """Stream reply from the agent."""
        async for chunk in self._agent.discuss(
            user_message=user_message,
            dispatch_client=self._client,
            project_cwd=self._cwd,
        ):
            yield chunk
