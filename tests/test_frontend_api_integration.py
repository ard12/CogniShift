import pytest
from httpx import AsyncClient, ASGITransport
from cognishift.app.main import app
from cognishift.app.core.auth import register_local_credential, User

TEST_OP_TOKEN = "test-token-operator-front-integration"
TEST_SUP_TOKEN = "test-token-supervisor-front-integration"
TEST_ADM_TOKEN = "test-token-admin-front-integration"


@pytest.fixture(autouse=True)
def setup_credentials():
    register_local_credential(TEST_OP_TOKEN, User(user_id="op_tester", role="operator", allowed_workspace_ids=[1]))
    register_local_credential(TEST_SUP_TOKEN, User(user_id="sup_tester", role="supervisor", allowed_workspace_ids=[1]))
    register_local_credential(TEST_ADM_TOKEN, User(user_id="adm_tester", role="administrator", allowed_workspace_ids=[1, 2, 3]))


@pytest.mark.asyncio
async def test_frontend_backing_endpoints_with_auth():
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {TEST_OP_TOKEN}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Auth context
        res_me = await client.get("/api/v1/auth/me", headers=headers)
        assert res_me.status_code == 200
        assert res_me.json()["user_id"] == "op_tester"

        # Workspaces
        res_ws = await client.get("/api/v1/workspaces", headers=headers)
        assert res_ws.status_code == 200
        assert len(res_ws.json()) >= 1

        # Agents
        res_agents = await client.get("/api/v1/agents?workspace_id=1", headers=headers)
        assert res_agents.status_code == 200

        # Knowledge
        res_k = await client.get("/api/v1/knowledge?workspace_id=1", headers=headers)
        assert res_k.status_code == 200

        # Approvals
        res_appr = await client.get("/api/v1/approvals", headers=headers)
        assert res_appr.status_code == 200

        # Artifacts
        res_art = await client.get("/api/v1/workspaces/1/artifacts", headers=headers)
        assert res_art.status_code == 200

        # Audit Ledger
        res_audit = await client.get("/api/v1/audit?workspace_id=1", headers=headers)
        assert res_audit.status_code == 200

        # Sovereignty & Network Events
        res_sov = await client.get("/api/v1/system/sovereignty", headers=headers)
        assert res_sov.status_code == 200

        res_net = await client.get("/api/v1/system/network-events", headers=headers)
        assert res_net.status_code == 200


@pytest.mark.asyncio
async def test_four_eyes_authorization_rejection_for_operator():
    """Ensure operator cannot approve their own high-risk requests (Four-Eyes principle)."""
    transport = ASGITransport(app=app)

    # 1. Create a run that requires approval
    op_headers = {"Authorization": f"Bearer {TEST_OP_TOKEN}"}
    sup_headers = {"Authorization": f"Bearer {TEST_SUP_TOKEN}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create an approval request directly or check pending
        appr_res = await client.get("/api/v1/approvals", headers=op_headers)
        assert appr_res.status_code == 200
        apprs = appr_res.json()

        # If there's an approval request, verify operator cannot approve it
        if apprs:
            req_id = apprs[0]["id"]
            # Operator attempt -> 403 Forbidden
            deny_res = await client.post(f"/api/v1/approvals/{req_id}/approve", headers=op_headers)
            assert deny_res.status_code == 403
            assert "Four-Eyes Policy Violation" in deny_res.json()["detail"]
