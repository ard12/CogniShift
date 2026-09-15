"""Comprehensive QA verification of the Four-Eyes Principle and Dual-Supervisor Authorization.

Covers:
- Sensitive action request creates 2-supervisor approval requirement (0/2)
- Requester self-approval rejected with 403 Forbidden
- Unprivileged operator approval rejected with 403 Forbidden
- First supervisor (Zara) provides Stage 1 approval (1/2, still pending)
- Notification FIRST_SUPERVISOR_APPROVAL dispatched
- Same supervisor (Zara) re-approval rejected with 403 Forbidden
- Second independent supervisor (Rakshita) provides Stage 2 approval (2/2, approved)
- Notification FOUR_EYES_COMPLETED dispatched
- Subsequent re-approval attempts on resolved request rejected
"""
import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from cognishift.app.core.auth import User, create_ephemeral_demo_session
from cognishift.app.db.database import get_db, init_db
from cognishift.app.main import app


@pytest.fixture(autouse=True)
async def init_fresh_db():
    await init_db()


@pytest.mark.asyncio
async def test_four_eyes_dual_supervisor_lifecycle():
    # Setup test personas
    op_user = User(user_id="operator_sam", role="operator", allowed_workspace_ids=[1])
    zara_user = User(user_id="zara", role="supervisor", allowed_workspace_ids=[1])
    rakshita_user = User(user_id="rakshita", role="supervisor", allowed_workspace_ids=[1])
    unauth_op = User(user_id="operator_bob", role="operator", allowed_workspace_ids=[1])

    op_tok, _ = create_ephemeral_demo_session(op_user)
    zara_tok, _ = create_ephemeral_demo_session(zara_user)
    rakshita_tok, _ = create_ephemeral_demo_session(rakshita_user)
    bob_tok, _ = create_ephemeral_demo_session(unauth_op)

    op_h = {"Authorization": f"Bearer {op_tok}"}
    zara_h = {"Authorization": f"Bearer {zara_tok}"}
    rakshita_h = {"Authorization": f"Bearer {rakshita_tok}"}
    bob_h = {"Authorization": f"Bearer {bob_tok}"}

    # Setup DB records for a sensitive action run
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (1, 'Plant Unit 1', 'test')")
        await db.execute("INSERT OR IGNORE INTO agent_definitions (id, workspace_id, name, description, system_instructions) VALUES (1, 1, 'Plant Agent', 'test', 'instructions')")
        await db.execute("INSERT OR IGNORE INTO tool_definitions (id, name, risk_level, requires_approval, enabled, implementation_key) VALUES (10, 'emergency_shutdown', 'sensitive', 1, 1, 'emergency_shutdown')")

        cur_run = await db.execute(
            "INSERT INTO agent_runs (workspace_id, agent_id, user_id, status, input_text) VALUES (1, 1, 'operator_sam', 'paused', 'Perform shutdown')"
        )
        run_id = cur_run.lastrowid

        cur_app = await db.execute(
            """INSERT INTO approval_requests (
                run_id, tool_id, status, request_reason, parameters, risk_level, required_approvals
            ) VALUES (?, 10, 'pending', 'Safety Interlock Procedure', '{"unit": "U-101"}', 'critical', 2)""",
            (run_id,),
        )
        app_id = cur_app.lastrowid
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Verify pending approvals list shows the request
        list_resp = await client.get("/api/v1/approvals", headers=zara_h)
        assert list_resp.status_code == 200
        pending_ids = [a["id"] for a in list_resp.json()]
        assert app_id in pending_ids

        # 2. Operator self-approval MUST be rejected
        self_resp = await client.post(f"/api/v1/approvals/{app_id}/approve", headers=op_h)
        assert self_resp.status_code == status.HTTP_403_FORBIDDEN
        assert "cannot approve their own request" in self_resp.json()["detail"].lower()

        # 3. Another unprivileged operator MUST be rejected (insufficient role)
        bob_resp = await client.post(f"/api/v1/approvals/{app_id}/approve", headers=bob_h)
        assert bob_resp.status_code == status.HTTP_403_FORBIDDEN
        assert "only 'supervisor' or 'administrator' can authorize" in bob_resp.json()["detail"].lower()

        # 4. Supervisor 1 (Zara) provides Stage 1 approval (1/2)
        zara_resp = await client.post(f"/api/v1/approvals/{app_id}/approve", headers=zara_h)
        assert zara_resp.status_code == 200
        zara_data = zara_resp.json()
        assert zara_data["status"] == "pending"  # Still pending second supervisor
        assert zara_data["reviewed_by"] == "zara"
        assert zara_data["reviewed_by_2"] is None

        # Verify Stage 1 audit log recorded
        async with get_db() as db:
            audit1 = await (await db.execute(
                "SELECT action, actor_id, details FROM audit_events WHERE resource_id = ? AND action = 'approval_stage_1_verified'",
                (app_id,),
            )).fetchone()
            assert audit1 is not None
            assert audit1["actor_id"] == "zara"

        # 5. Same supervisor (Zara) attempts to approve again -> MUST BE REJECTED
        zara_reapprove = await client.post(f"/api/v1/approvals/{app_id}/approve", headers=zara_h)
        assert zara_reapprove.status_code == status.HTTP_403_FORBIDDEN
        assert "four-eyes policy violation" in zara_reapprove.json()["detail"].lower()
        assert "stage 2 must be authorized by an independent, different supervisor" in zara_reapprove.json()["detail"].lower()

        # 6. Supervisor 2 (Rakshita) provides Stage 2 approval (2/2) -> APPROVED
        rakshita_resp = await client.post(f"/api/v1/approvals/{app_id}/approve", headers=rakshita_h)
        assert rakshita_resp.status_code == 200
        final_data = rakshita_resp.json()
        assert final_data["status"] == "approved"
        assert final_data["reviewed_by"] == "zara"
        assert final_data["reviewed_by_2"] == "rakshita"

        # Verify Stage 2 audit log recorded
        async with get_db() as db:
            audit2 = await (await db.execute(
                "SELECT action, actor_id, details FROM audit_events WHERE resource_id = ? AND action = 'approval_stage_2_authorized'",
                (app_id,),
            )).fetchone()
            assert audit2 is not None
            assert audit2["actor_id"] == "rakshita"

        # 7. Attempting to approve again on already resolved request -> 400 Bad Request
        re_approve_done = await client.post(f"/api/v1/approvals/{app_id}/approve", headers=rakshita_h)
        assert re_approve_done.status_code == status.HTTP_400_BAD_REQUEST
        assert "already approved" in re_approve_done.json()["detail"].lower()

        # 8. Verify internal notifications dispatched for both stages
        async with get_db() as db:
            stage1_alert = await (await db.execute(
                "SELECT alert_type, recipients, severity FROM offline_security_alerts WHERE alert_type = 'FIRST_SUPERVISOR_APPROVAL' ORDER BY id DESC LIMIT 1"
            )).fetchone()
            assert stage1_alert is not None
            assert "rakshita@secure.internal" in stage1_alert["recipients"]

            stage2_alert = await (await db.execute(
                "SELECT alert_type, recipients, severity FROM offline_security_alerts WHERE alert_type = 'FOUR_EYES_COMPLETED' ORDER BY id DESC LIMIT 1"
            )).fetchone()
            assert stage2_alert is not None
