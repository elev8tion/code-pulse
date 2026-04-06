"""Tests for SubAgentPool rotation."""
import pytest
from codepulse.agents.pool import SubAgentPool


def test_initial_slot():
    pool = SubAgentPool(size=3)
    assert pool.current_slot == 0
    assert pool.current.slot_id == 0


def test_rotation():
    pool = SubAgentPool(size=3)
    pool.rotate("synopsis 1")
    assert pool.current_slot == 1
    pool.rotate("synopsis 2")
    assert pool.current_slot == 2
    pool.rotate("synopsis 3")
    assert pool.current_slot == 0  # wraps


def test_handoff_received():
    pool = SubAgentPool(size=3)
    pool.rotate("my synopsis")
    assert pool.current.synopsis == "my synopsis"


def test_restore_slot():
    pool = SubAgentPool(size=3)
    pool.restore_slot(2)
    assert pool.current_slot == 2


def test_all_agents_length():
    pool = SubAgentPool(size=3)
    assert len(pool.all_agents()) == 3
