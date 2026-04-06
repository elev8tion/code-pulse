"""Tests for SessionManager."""
import pytest
from pathlib import Path
import tempfile
import os

from codepulse.session.manager import SessionManager
from codepulse.session.models import Session
from codepulse.utils.time_utils import today_str


def test_load_or_create_new(tmp_path, monkeypatch):
    # Point CODEPULSE_HOME to tmp_path
    monkeypatch.setattr("codepulse.config.CODEPULSE_HOME", tmp_path)
    monkeypatch.setattr("codepulse.config.PROJECTS_DIR", tmp_path / "projects")
    import codepulse.utils.paths as paths_mod
    monkeypatch.setattr(paths_mod, "PROJECTS_DIR", tmp_path / "projects")

    mgr = SessionManager("test-project", tmp_path / "my-project")
    session = mgr.load_or_create()
    assert isinstance(session, Session)
    assert session.project_name == "test-project"
    assert session.turn_count == 0


def test_append_turn(tmp_path, monkeypatch):
    monkeypatch.setattr("codepulse.config.PROJECTS_DIR", tmp_path / "projects")
    import codepulse.utils.paths as paths_mod
    monkeypatch.setattr(paths_mod, "PROJECTS_DIR", tmp_path / "projects")

    mgr = SessionManager("test-project", tmp_path)
    session = mgr.load_or_create()
    turn = mgr.append_turn(
        session=session,
        user_msg="hello",
        assistant_msg="hi there",
        diff_snapshot=None,
        synopsis="no changes",
        agent_slot=0,
    )
    assert turn.turn_index == 1
    assert session.turn_count == 1
