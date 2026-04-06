"""SubAgentPool — round-robin rotation."""
from __future__ import annotations

from codepulse.agents.subagent import SubAgent
from codepulse.config import AGENT_POOL_SIZE, AGENT_CONTEXT_WINDOW


class SubAgentPool:
    def __init__(
        self,
        size: int = AGENT_POOL_SIZE,
        context_window_size: int = AGENT_CONTEXT_WINDOW,
    ) -> None:
        self._agents = [SubAgent(slot_id=i, context_window_size=context_window_size) for i in range(size)]
        self._current = 0

    @property
    def current(self) -> SubAgent:
        return self._agents[self._current]

    @property
    def current_slot(self) -> int:
        return self._current

    @property
    def size(self) -> int:
        return len(self._agents)

    def rotate(self, synopsis: str) -> SubAgent:
        """Hand off synopsis to next agent, advance pointer."""
        next_slot = (self._current + 1) % len(self._agents)
        self._agents[next_slot].receive_handoff(synopsis)
        self._current = next_slot
        return self._agents[self._current]

    def get_agent(self, slot: int) -> SubAgent:
        return self._agents[slot % len(self._agents)]

    def all_agents(self) -> list[SubAgent]:
        return list(self._agents)

    def restore_slot(self, slot: int) -> None:
        """Restore pool pointer from persisted session."""
        self._current = slot % len(self._agents)
