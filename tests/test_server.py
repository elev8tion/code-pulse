"""Tests for the FastAPI server endpoints."""
import pytest
import os
from pathlib import Path


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a TestClient with a temporary project directory."""
    monkeypatch.setenv("CODEPULSE_PROJECT_PATH", str(tmp_path))
    monkeypatch.setenv("CODEPULSE_PROJECT_NAME", "test-server-project")
    monkeypatch.setenv("CODEPULSE_RESUME", "0")
    monkeypatch.setattr("codepulse.config.PROJECTS_DIR", tmp_path / "projects")

    import codepulse.utils.paths as paths_mod
    monkeypatch.setattr(paths_mod, "PROJECTS_DIR", tmp_path / "projects")

    # Re-import server with patched state
    import importlib
    import codepulse.server as server_mod
    importlib.reload(server_mod)

    from httpx import AsyncClient, ASGITransport
    import asyncio

    # Initialize state
    loop = asyncio.new_event_loop()
    loop.run_until_complete(server_mod.state.initialize())
    loop.close()

    return AsyncClient(
        transport=ASGITransport(app=server_mod.app),
        base_url="http://test",
    )


@pytest.mark.asyncio
async def test_health(client):
    async with client as c:
        response = await c.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_get_session(client):
    async with client as c:
        response = await c.get("/api/session")
        assert response.status_code == 200
        data = response.json()
        assert data["turn_count"] == 0
        assert data["agent_pool_size"] == 3
        assert data["is_streaming"] is False


@pytest.mark.asyncio
async def test_get_agents(client):
    async with client as c:
        response = await c.get("/api/agents")
        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 3
        assert agents[0]["slot_id"] == 0
        assert agents[0]["is_current"] is True
        assert agents[0]["state"] == "sleeping"


@pytest.mark.asyncio
async def test_get_heatmap(client):
    async with client as c:
        response = await c.get("/api/heatmap")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "max_touch_count" in data
        assert data["max_touch_count"] == 0


@pytest.mark.asyncio
async def test_get_actions(client):
    async with client as c:
        response = await c.get("/api/actions")
        assert response.status_code == 200
        actions = response.json()
        assert len(actions) > 0
        assert any(a["id"] == "fix-bugs" for a in actions)
        assert any(a["id"] == "write-tests" for a in actions)


@pytest.mark.asyncio
async def test_get_processes(client):
    async with client as c:
        response = await c.get("/api/processes")
        assert response.status_code == 200
        processes = response.json()
        assert isinstance(processes, list)


@pytest.mark.asyncio
async def test_command_help(client):
    async with client as c:
        response = await c.post("/api/command", json={"command": "/help"})
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "/help" in data["response"]


@pytest.mark.asyncio
async def test_command_unknown(client):
    async with client as c:
        response = await c.post("/api/command", json={"command": "/unknown-command"})
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_discuss_toggle(client):
    async with client as c:
        # Open discussion
        response = await c.post("/api/discuss/toggle")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is True

        # Close discussion
        response = await c.post("/api/discuss/toggle")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is False


@pytest.mark.asyncio
async def test_fire_unknown_action(client):
    async with client as c:
        response = await c.post("/api/action/nonexistent-action", json={})
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_toggle_unknown_process(client):
    async with client as c:
        response = await c.post("/api/process/nonexistent-process/toggle")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_projects(client):
    async with client as c:
        response = await c.get("/api/projects")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
