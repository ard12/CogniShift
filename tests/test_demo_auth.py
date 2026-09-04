import json
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from cognishift.app.config import settings
from cognishift.app.core import auth as auth_core
from cognishift.app.main import app
from cognishift.app.api import sandbox as sandbox_api
from cognishift.core.sandbox.schemas import SandboxStatus


@pytest.mark.asyncio
async def test_demo_session_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "cognishift_demo_mode", False)
    transport = ASGITransport(app=app, client=("127.0.0.1", 12345))
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.post("/api/v1/auth/demo-session", json={"persona_id": "operator"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_demo_session_rejects_non_loopback(monkeypatch):
    monkeypatch.setattr(settings, "cognishift_demo_mode", True)
    monkeypatch.setattr(settings, "operating_mode", "local")
    transport = ASGITransport(app=app, client=("192.168.10.20", 12345))
    async with AsyncClient(transport=transport, base_url="http://cognishift.local") as client:
        response = await client.post("/api/v1/auth/demo-session", json={"persona_id": "operator"})
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("persona_id", "user_id", "role"),
    [
        ("operator", "operator_sam", "operator"),
        ("supervisor", "supervisor_jane", "supervisor"),
        ("administrator", "admin_rohit", "administrator"),
    ],
)
async def test_local_demo_persona_creates_ephemeral_verified_session(monkeypatch, persona_id, user_id, role):
    monkeypatch.setattr(settings, "cognishift_demo_mode", True)
    monkeypatch.setattr(settings, "operating_mode", "local")
    transport = ASGITransport(app=app, client=("127.0.0.1", 12345))
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        session_response = await client.post("/api/v1/auth/demo-session", json={"persona_id": persona_id})
        assert session_response.status_code == 200
        payload = session_response.json()
        assert set(payload) == {"session_token", "expires_in_seconds"}
        token = payload["session_token"]
        assert token
        assert auth_core.hash_token(token) in auth_core.EPHEMERAL_DEMO_SESSIONS
        assert auth_core.hash_token(token) not in auth_core.LOCAL_CREDENTIAL_STORE

        me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["user_id"] == user_id
        assert me.json()["role"] == role


@pytest.mark.asyncio
async def test_changed_credential_store_reloads_without_server_restart(monkeypatch, tmp_path):
    store_path = tmp_path / "auth_store.json"
    monkeypatch.setattr(settings, "auth_store_path", store_path)
    auth_core.LOCAL_CREDENTIAL_STORE.clear()
    auth_core.register_local_credential(
        "old-token", auth_core.User(user_id="old_user", role="operator", allowed_workspace_ids=[1])
    )
    auth_core.save_credential_store(store_path)

    fresh_token = "fresh-token-with-surrounding-whitespace"
    store_path.write_text(json.dumps({
        "users": [{
            "credential_hash": auth_core.hash_token(fresh_token),
            "user_id": "operator_sam",
            "role": "operator",
            "allowed_workspace_ids": [1],
            "enabled": True,
        }]
    }), encoding="utf-8")

    transport = ASGITransport(app=app, client=("127.0.0.1", 12345))
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer   {fresh_token}   "},
        )
    assert response.status_code == 200
    assert response.json()["user_id"] == "operator_sam"


@pytest.mark.asyncio
async def test_sandbox_api_stages_demo_input_as_workspace_relative_path(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()
    (demo_dir / "equipment_readings.csv").write_text("tag,value\nPT-101,492.5\n", encoding="utf-8")
    captured = {}

    async def fake_execute(workspace_id, run_id, request):
        captured["request"] = request
        return SimpleNamespace(
            status=SandboxStatus.SUCCESS,
            exit_code=0,
            stdout="ok",
            stderr="",
            duration_ms=1,
            promoted_artifact_ids=[],
            output_files=[],
        )

    monkeypatch.setattr(sandbox_api, "execute_sandbox_code", fake_execute)
    transport = ASGITransport(app=app, client=("127.0.0.1", 12345))
    headers = {"Authorization": "Bearer test-token-admin-112"}
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.post(
            "/api/v1/sandbox/execute",
            headers=headers,
            json={"workspace_id": 1, "code": "print('ok')", "input_filename": "equipment_readings.csv"},
        )
    assert response.status_code == 200
    input_ref = captured["request"].input_files[0]
    assert input_ref.source_path == "documents/demo_inputs/equipment_readings.csv"
    assert not __import__("pathlib").Path(input_ref.source_path).is_absolute()


@pytest.mark.asyncio
async def test_sandbox_api_rejects_unapproved_input_filename():
    transport = ASGITransport(app=app, client=("127.0.0.1", 12345))
    headers = {"Authorization": "Bearer test-token-admin-112"}
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.post(
            "/api/v1/sandbox/execute",
            headers=headers,
            json={"workspace_id": 1, "code": "print('ok')", "input_filename": "../private/auth_store.json"},
        )
    assert response.status_code == 400
