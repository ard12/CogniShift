from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from cognishift.app.main import app
from cognishift.app.core.auth import register_local_credential, User, hash_token, LOCAL_CREDENTIAL_STORE
from cognishift.app.db.database import get_db, init_db

OP_TOKEN = "test-token-auth-operator-111"
SUP_TOKEN = "test-token-auth-supervisor-222"
ADM_TOKEN = "test-token-auth-admin-333"


@pytest.fixture(autouse=True)
def setup_test_credentials():
    register_local_credential(OP_TOKEN, User(user_id="test_op", role="operator", allowed_workspace_ids=[1]))
    register_local_credential(SUP_TOKEN, User(user_id="test_sup", role="supervisor", allowed_workspace_ids=[1, 2]))
    register_local_credential(ADM_TOKEN, User(user_id="test_adm", role="administrator", allowed_workspace_ids=[1, 2, 3]))


@pytest.mark.asyncio
async def test_auth_me_unauthorized():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/auth/me")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_invalid_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer totally-fake-token"})
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_valid_tokens():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Operator
        res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {OP_TOKEN}"})
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == "test_op"
        assert data["role"] == "operator"
        assert 1 in data["allowed_workspace_ids"]

        # Supervisor
        res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {SUP_TOKEN}"})
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == "test_sup"
        assert data["role"] == "supervisor"

        # Administrator
        res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ADM_TOKEN}"})
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == "test_adm"
        assert data["role"] == "administrator"


@pytest.mark.asyncio
async def test_demo_personas_never_returns_credentials():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/auth/demo-personas")
        assert res.status_code == 200
        personas = res.json()
        assert len(personas) >= 3

        # ABSOLUTE RULE: Zero credentials leaked
        for p in personas:
            assert "persona_id" in p
            assert "display_name" in p
            assert "role" in p
            assert "token" not in p
            assert "key" not in p
            assert "password" not in p
            assert "credential" not in p
            assert "secret" not in p


@pytest.mark.asyncio
async def test_audit_endpoint_access_control():
    await init_db()
    # Insert a test audit event
    async with get_db() as db:
        await db.execute(
            """INSERT INTO audit_events (workspace_id, actor_id, action, resource_type, resource_id, details, result)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (1, "test_actor", "EXECUTE_TOOL", "tool", 1, "test details", "SUCCESS")
        )
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unauthenticated -> 401
        res = await client.get("/api/v1/audit")
        assert res.status_code == 401

        # 2. Authenticated operator accessing allowed workspace 1 -> 200
        res = await client.get("/api/v1/audit?workspace_id=1", headers={"Authorization": f"Bearer {OP_TOKEN}"})
        assert res.status_code == 200
        events = res.json()
        assert isinstance(events, list)
        assert len(events) >= 1
        assert events[0]["action"] == "EXECUTE_TOOL"

        # 3. Authenticated operator attempting to access unauthorized workspace 2 -> 403 Forbidden
        res = await client.get("/api/v1/audit?workspace_id=2", headers={"Authorization": f"Bearer {OP_TOKEN}"})
        assert res.status_code == 403

        # 4. Authenticated supervisor accessing workspace 2 -> 200
        res = await client.get("/api/v1/audit?workspace_id=2", headers={"Authorization": f"Bearer {SUP_TOKEN}"})
        assert res.status_code == 200

        # 5. Authenticated administrator accessing all workspaces -> 200
        res = await client.get("/api/v1/audit", headers={"Authorization": f"Bearer {ADM_TOKEN}"})
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_real_sqlite_row_supports_two_stage_approval():
    """Regression: approval handlers must not treat sqlite3.Row as a dict with .get()."""
    await init_db()
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (1, 'Approval Regression', 'isolated test')"
        )
        await db.execute(
            """INSERT OR IGNORE INTO tool_definitions
               (id, name, description, risk_level, requires_approval, implementation_key)
               VALUES (7001, 'approval_regression_tool', 'test tool', 'service_interrupting', 1, 'test')"""
        )
        run_cursor = await db.execute(
            """INSERT INTO agent_runs (workspace_id, agent_id, status, user_id, input_text)
               VALUES (1, 1, 'paused', 'test_op', 'approval regression') RETURNING id"""
        )
        run_id = (await run_cursor.fetchone())["id"]
        approval_cursor = await db.execute(
            """INSERT INTO approval_requests
               (run_id, tool_id, status, request_reason, risk_level, required_approvals)
               VALUES (?, 7001, 'pending', 'verify sqlite row handling', 'service_interrupting', 2)
               RETURNING id""",
            (run_id,),
        )
        approval_id = (await approval_cursor.fetchone())["id"]
        await db.commit()

    transport = ASGITransport(app=app)
    with patch("cognishift.app.api.approvals.resume_agent_run", new=AsyncMock()) as resume_mock:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post(
                f"/api/v1/approvals/{approval_id}/approve",
                headers={"Authorization": f"Bearer {SUP_TOKEN}"},
            )
            assert first.status_code == 200
            assert first.json()["status"] == "pending"
            assert first.json()["reviewed_by"] == "test_sup"

            second = await client.post(
                f"/api/v1/approvals/{approval_id}/approve",
                headers={"Authorization": f"Bearer {ADM_TOKEN}"},
            )
            assert second.status_code == 200
            assert second.json()["status"] == "approved"
            assert second.json()["reviewed_by_2"] == "test_adm"

        resume_mock.assert_awaited_once_with(run_id)
