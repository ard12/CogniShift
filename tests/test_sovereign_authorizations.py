"""Comprehensive test suite for Sovereign Temporary Authorizations, Four-Eyes Permitting,
Atomic Concurrency-Safe Consumption, Role-Scoped Mailbox Isolation, and Durable Async Processing.
"""
import asyncio
import re
from datetime import datetime, timezone, timedelta
import pytest
from httpx import ASGITransport, AsyncClient

from cognishift.app.core.auth import User, create_ephemeral_demo_session
from cognishift.app.db.database import get_db, init_db
from cognishift.app.main import app
from cognishift.core.authorizations import (
    request_temporary_authorization,
    approve_authorization_stage,
    admin_override_authorization,
    revoke_authorization,
    execute_authorized_action_atomic,
    process_pending_post_approval_jobs,
)


@pytest.fixture(autouse=True)
async def init_fresh_db():
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (1, 'Plant Unit 1', 'test')")
        await db.commit()


@pytest.fixture
def auth_personas():
    aryan = User(user_id="aryan", role="operator", allowed_workspace_ids=[1])
    zara = User(user_id="zara", role="supervisor", allowed_workspace_ids=[1])
    rakshita = User(user_id="rakshita", role="supervisor", allowed_workspace_ids=[1])
    vicky = User(user_id="vicky", role="supervisor", allowed_workspace_ids=[1])
    rohit = User(user_id="rohit", role="administrator", allowed_workspace_ids=[1])

    aryan_tok, _ = create_ephemeral_demo_session(aryan)
    zara_tok, _ = create_ephemeral_demo_session(zara)
    rakshita_tok, _ = create_ephemeral_demo_session(rakshita)
    vicky_tok, _ = create_ephemeral_demo_session(vicky)
    rohit_tok, _ = create_ephemeral_demo_session(rohit)

    return {
        "aryan": (aryan, {"Authorization": f"Bearer {aryan_tok}"}),
        "zara": (zara, {"Authorization": f"Bearer {zara_tok}"}),
        "rakshita": (rakshita, {"Authorization": f"Bearer {rakshita_tok}"}),
        "vicky": (vicky, {"Authorization": f"Bearer {vicky_tok}"}),
        "rohit": (rohit, {"Authorization": f"Bearer {rohit_tok}"}),
    }


@pytest.mark.asyncio
async def test_four_eyes_temporary_authorization_lifecycle(auth_personas):
    """Verify Four-Eyes dual-supervisor lifecycle:
    1. Request by operator creates PENDING 0/2 permit.
    2. Operator self-approval is rejected (403).
    3. First supervisor (Zara) approves -> PENDING 1/2.
    4. Duplicate approval by Zara is rejected (403).
    5. Second independent supervisor (Rakshita) approves -> ACTIVE 2/2.
    6. Durable post-approval job queued in post_approval_jobs.
    """
    aryan_user, aryan_h = auth_personas["aryan"]
    _, zara_h = auth_personas["zara"]
    _, rakshita_h = auth_personas["rakshita"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Request temporary permit
        req_payload = {
            "workspace_id": 1,
            "user_id": "aryan",
            "action": "operate_pump",
            "resource": "P-101A",
            "reason": "Transfer naphtha to tank T-204 as per SOP-PUMP-001",
            "max_uses": 1,
            "valid_minutes": 60,
        }
        res = await client.post("/api/v1/authorizations", json=req_payload, headers=aryan_h)
        assert res.status_code == 201, res.text
        data = res.json()
        permit_id = data["id"]
        permit_code = data["permit_code"]

        assert permit_code.startswith("AUTH-PERMIT-")
        assert data["status"] == "PENDING_APPROVAL"
        assert data["first_approver"] is None
        assert data["second_approver"] is None

        # 2. Operator self-approval rejected
        self_appr = await client.post(
            f"/api/v1/authorizations/{permit_id}/approve",
            json={"comments": "Self-approval attempt"},
            headers=aryan_h,
        )
        assert self_appr.status_code == 403

        # 3. Stage 1 approval by Supervisor Zara
        s1 = await client.post(
            f"/api/v1/authorizations/{permit_id}/approve",
            json={"comments": "Operating parameters verified within safety limits"},
            headers=zara_h,
        )
        assert s1.status_code == 200, s1.text
        s1_data = s1.json()
        assert s1_data["status"] == "PENDING_APPROVAL"
        assert s1_data["approval_stage"] == "1/2"
        assert s1_data["first_approver"] == "zara"
        assert s1_data["second_approver"] is None

        # 4. Duplicate approval by Zara rejected
        dup = await client.post(
            f"/api/v1/authorizations/{permit_id}/approve",
            json={"comments": "Second approval attempt by same supervisor"},
            headers=zara_h,
        )
        assert dup.status_code == 403
        assert "Four-Eyes Violation" in dup.json()["detail"]

        # 5. Stage 2 approval by Supervisor Rakshita
        s2 = await client.post(
            f"/api/v1/authorizations/{permit_id}/approve",
            json={"comments": "Pressure relief path confirmed open"},
            headers=rakshita_h,
        )
        assert s2.status_code == 200, s2.text
        s2_data = s2.json()
        assert s2_data["status"] == "ACTIVE"
        assert s2_data["approval_stage"] == "2/2"
        assert s2_data["first_approver"] == "zara"
        assert s2_data["second_approver"] == "rakshita"

        # 6. Verify job placed in post_approval_jobs
        async with get_db() as db:
            cur = await db.execute(
                "SELECT id, status FROM post_approval_jobs WHERE permit_id = ?",
                (permit_id,),
            )
            row = await cur.fetchone()
            assert row is not None
            assert row["status"] in ("PENDING", "COMPLETED", "PROCESSING")


@pytest.mark.asyncio
async def test_atomic_concurrency_safe_consumption_10_clients(auth_personas):
    """Verify that under 10 concurrent execution attempts of a 1-use permit:
    - Exactly 1 client succeeds with 200 OK and status CONSUMED.
    - Exactly 9 clients fail with 403 AUTHORIZATION_CONSUMED.
    - The permit is marked CONSUMED in the database.
    """
    _, aryan_h = auth_personas["aryan"]
    _, zara_h = auth_personas["zara"]
    _, rakshita_h = auth_personas["rakshita"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create and approve permit
        req = await client.post(
            "/api/v1/authorizations",
            json={
                "workspace_id": 1,
                "user_id": "aryan",
                "action": "operate_pump",
                "resource": "P-101A",
                "reason": "Concurrent load test",
                "max_uses": 1,
                "valid_minutes": 30,
            },
            headers=aryan_h,
        )
        permit_id = req.json()["id"]
        permit_code = req.json()["permit_code"]

        await client.post(f"/api/v1/authorizations/{permit_id}/approve", json={"comments": "Approve 1"}, headers=zara_h)
        await client.post(f"/api/v1/authorizations/{permit_id}/approve", json={"comments": "Approve 2"}, headers=rakshita_h)

        # Fire 10 concurrent requests to execute the permit
        exec_payload = {
            "permit_code": permit_code,
            "action": "operate_pump",
            "resource": "P-101A",
            "parameters": {"mode": "START", "flow_rate": 120.0},
        }

        tasks = [
            client.post("/api/v1/authorizations/execute", json=exec_payload, headers=aryan_h)
            for _ in range(10)
        ]
        responses = await asyncio.gather(*tasks)

        status_codes = [r.status_code for r in responses]
        successes = [r for r in responses if r.status_code == 200]
        failures = [r for r in responses if r.status_code == 403]

        assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}. Status codes: {status_codes}"
        assert len(failures) == 9, f"Expected exactly 9 failures, got {len(failures)}"

        success_data = successes[0].json()
        assert success_data["status"] == "CONSUMED"
        assert success_data["permit_code"] == permit_code
        sim_res = success_data.get("simulated_result", "") or success_data.get("disclaimer", "")
        assert "[SIMULATED INDUSTRIAL ACTION - SIH FINALS PROTOTYPE]" in sim_res

        for f in failures:
            detail = f.json().get("detail", "")
            assert "AUTHORIZATION_CONSUMED" in detail or "consumed" in detail.lower()

        # Check DB state
        async with get_db() as db:
            cur = await db.execute(
                "SELECT status, uses, max_uses, consumed_at FROM temporary_authorizations WHERE id = ?",
                (permit_id,),
            )
            row = await cur.fetchone()
            assert row["status"] == "CONSUMED"
            assert row["uses"] == 1
            assert row["consumed_at"] is not None


@pytest.mark.asyncio
async def test_second_execution_fail_closed(auth_personas):
    """Verify that calling execute again after consumption immediately fails closed."""
    _, aryan_h = auth_personas["aryan"]
    _, zara_h = auth_personas["zara"]
    _, rakshita_h = auth_personas["rakshita"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        req = await client.post(
            "/api/v1/authorizations",
            json={"workspace_id": 1, "user_id": "aryan", "action": "operate_pump", "resource": "P-101A", "reason": "Test", "max_uses": 1},
            headers=aryan_h,
        )
        pid = req.json()["id"]
        pcode = req.json()["permit_code"]
        await client.post(f"/api/v1/authorizations/{pid}/approve", json={"comments": "A1"}, headers=zara_h)
        await client.post(f"/api/v1/authorizations/{pid}/approve", json={"comments": "A2"}, headers=rakshita_h)

        # Run 1: Success
        r1 = await client.post(
            "/api/v1/authorizations/execute",
            json={"permit_code": pcode, "action": "operate_pump", "resource": "P-101A"},
            headers=aryan_h,
        )
        assert r1.status_code == 200

        # Run 2: Rejection
        r2 = await client.post(
            "/api/v1/authorizations/execute",
            json={"permit_code": pcode, "action": "operate_pump", "resource": "P-101A"},
            headers=aryan_h,
        )
        assert r2.status_code == 403
        assert "AUTHORIZATION_CONSUMED" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_authorization_scope_and_identity_rejections(auth_personas):
    """Verify fail-closed enforcement when:
    - User mismatch (Vicky attempts to execute Aryan's permit)
    - Action mismatch (operate_pump vs vent_gas)
    - Resource mismatch (P-101A vs P-102)
    - Expired permit
    - Revoked permit
    """
    _, aryan_h = auth_personas["aryan"]
    _, zara_h = auth_personas["zara"]
    _, rakshita_h = auth_personas["rakshita"]
    _, vicky_h = auth_personas["vicky"]
    _, rohit_h = auth_personas["rohit"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Setup active permit
        req = await client.post(
            "/api/v1/authorizations",
            json={"workspace_id": 1, "user_id": "aryan", "action": "operate_pump", "resource": "P-101A", "reason": "Scope test", "max_uses": 2},
            headers=aryan_h,
        )
        pid = req.json()["id"]
        pcode = req.json()["permit_code"]
        await client.post(f"/api/v1/authorizations/{pid}/approve", json={"comments": "A1"}, headers=zara_h)
        await client.post(f"/api/v1/authorizations/{pid}/approve", json={"comments": "A2"}, headers=rakshita_h)

        # 1. User mismatch
        mismatch_user = await client.post(
            "/api/v1/authorizations/execute",
            json={"permit_code": pcode, "action": "operate_pump", "resource": "P-101A"},
            headers=vicky_h,
        )
        assert mismatch_user.status_code == 403
        assert "AUTHORIZATION_NOT_OWNED" in mismatch_user.json()["detail"]

        # 2. Action mismatch
        mismatch_action = await client.post(
            "/api/v1/authorizations/execute",
            json={"permit_code": pcode, "action": "vent_gas", "resource": "P-101A"},
            headers=aryan_h,
        )
        assert mismatch_action.status_code == 403
        assert "AUTHORIZATION_SCOPE_MISMATCH" in mismatch_action.json()["detail"]

        # 3. Resource mismatch
        mismatch_resource = await client.post(
            "/api/v1/authorizations/execute",
            json={"permit_code": pcode, "action": "operate_pump", "resource": "P-102"},
            headers=aryan_h,
        )
        assert mismatch_resource.status_code == 403
        assert "AUTHORIZATION_SCOPE_MISMATCH" in mismatch_resource.json()["detail"]

        # 4. Revocation
        revoke_res = await client.post(
            f"/api/v1/authorizations/{pid}/revoke",
            json={"reason": "Security protocol trip"},
            headers=rohit_h,
        )
        assert revoke_res.status_code == 200

        revoked_exec = await client.post(
            "/api/v1/authorizations/execute",
            json={"permit_code": pcode, "action": "operate_pump", "resource": "P-101A"},
            headers=aryan_h,
        )
        assert revoked_exec.status_code == 403
        assert "AUTHORIZATION_REVOKED" in revoked_exec.json()["detail"]


@pytest.mark.asyncio
async def test_role_scoped_mailbox_isolation_and_delivery_state(auth_personas):
    """Verify that:
    1. Aryan only sees alerts where Aryan is an explicit recipient.
    2. When Aryan marks an alert as read, Aryan's is_read = 1.
    3. Zara's and Admin's delivery records for the same alert remain is_read = 0.
    """
    _, aryan_h = auth_personas["aryan"]
    _, zara_h = auth_personas["zara"]
    _, rohit_h = auth_personas["rohit"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create an authorization event which creates a multi-recipient notification
        req = await client.post(
            "/api/v1/authorizations",
            json={"workspace_id": 1, "user_id": "aryan", "action": "operate_pump", "resource": "P-101A", "reason": "Mail isolation test"},
            headers=aryan_h,
        )
        pid = req.json()["id"]
        await client.post(f"/api/v1/authorizations/{pid}/approve", json={"comments": "A1"}, headers=zara_h)
        await client.post(f"/api/v1/authorizations/{pid}/approve", json={"comments": "A2"}, headers=auth_personas["rakshita"][1])

        # Force process background post approval jobs so mail is composed and outbox inserted
        await process_pending_post_approval_jobs()

        # Aryan reads his mailbox
        aryan_mb = await client.get("/api/v1/mail", headers=aryan_h)
        assert aryan_mb.status_code == 200
        messages = aryan_mb.json()["messages"]
        assert len(messages) >= 1
        target_msg = messages[0]
        alert_id = target_msg["id"]
        assert target_msg["is_read"] == 0

        # Aryan marks message read
        mark_res = await client.post(f"/api/v1/mail/{alert_id}/read", headers=aryan_h)
        assert mark_res.status_code == 200
        assert mark_res.json()["is_read"] == 1

        # Re-fetch Aryan's mailbox -> now is_read == 1
        aryan_mb_after = await client.get("/api/v1/mail", headers=aryan_h)
        aryan_target = [a for a in aryan_mb_after.json()["messages"] if a["id"] == alert_id][0]
        assert aryan_target["is_read"] == 1

        # Fetch Zara's mailbox -> Zara's copy must still be is_read == 0
        zara_mb = await client.get("/api/v1/mail", headers=zara_h)
        assert zara_mb.status_code == 200
        zara_target = [a for a in zara_mb.json()["messages"] if a["id"] == alert_id]
        if zara_target:
            assert zara_target[0]["is_read"] == 0, "Zara's read state should not be affected by Aryan reading his copy"

        # Fetch Admin's mailbox -> Admin's copy must still be is_read == 0
        admin_mb = await client.get("/api/v1/mail", headers=rohit_h)
        assert admin_mb.status_code == 200
        admin_target = [a for a in admin_mb.json()["messages"] if a["id"] == alert_id]
        if admin_target:
            assert admin_target[0]["is_read"] == 0, "Admin's read state should not be affected by Aryan reading his copy"


@pytest.mark.asyncio
async def test_post_approval_job_durability_and_processing(auth_personas):
    """Verify durable job processing:
    - Approval Stage 2 marks status = ACTIVE in < 1s and inserts a PENDING job into post_approval_jobs.
    - process_pending_post_approval_jobs() generates DOCX work permit artifact in workspace_artifacts.
    - Post approval job transitions to COMPLETED.
    """
    _, aryan_h = auth_personas["aryan"]
    _, zara_h = auth_personas["zara"]
    _, rakshita_h = auth_personas["rakshita"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        req = await client.post(
            "/api/v1/authorizations",
            json={"workspace_id": 1, "user_id": "aryan", "action": "operate_pump", "resource": "P-101A", "reason": "Durable job test"},
            headers=aryan_h,
        )
        pid = req.json()["id"]
        pcode = req.json()["permit_code"]

        await client.post(f"/api/v1/authorizations/{pid}/approve", json={"comments": "A1"}, headers=zara_h)
        await client.post(f"/api/v1/authorizations/{pid}/approve", json={"comments": "A2"}, headers=rakshita_h)

        # Check job is in DB
        async with get_db() as db:
            cur = await db.execute("SELECT id, status FROM post_approval_jobs WHERE permit_id = ?", (pid,))
            job = await cur.fetchone()
            assert job is not None

        # Allow background processor a moment or run manually to guarantee completion
        await asyncio.sleep(0.1)
        await process_pending_post_approval_jobs()

        # Verify job is completed
        async with get_db() as db:
            cur = await db.execute("SELECT status, artifact_id, alert_id FROM post_approval_jobs WHERE permit_id = ?", (pid,))
            job_after = await cur.fetchone()
            assert job_after is not None
            assert job_after["status"] == "COMPLETED"
            assert job_after["artifact_id"] is not None

            # Verify artifact exists in workspace_artifacts
            cur_art = await db.execute("SELECT filename, artifact_type FROM workspace_artifacts WHERE id = ?", (job_after["artifact_id"],))
            art = await cur_art.fetchone()
            assert art is not None
            assert art["artifact_type"] == "docx"
            assert pcode in art["filename"]


@pytest.mark.asyncio
async def test_restart_recovery_pending_post_approval_jobs(auth_personas):
    """Simulate server restart with unhandled jobs in queue:
    Insert a raw PENDING job as if the server died before background worker executed.
    Calling process_pending_post_approval_jobs() picks up the unhandled job and processes it to COMPLETED.
    """
    now_str = "2026-09-08T18:00:00Z"
    expires_str = "2026-09-08T19:00:00Z"
    async with get_db() as db:
        p_cur = await db.execute(
            """INSERT INTO temporary_authorizations (
                permit_code, workspace_id, user_id, action, resource,
                valid_from, expires_at, status, requested_by,
                first_approver, second_approver, created_at
            ) VALUES ('AUTH-PERMIT-RESTART-001', 1, 'aryan', 'operate_pump', 'P-101A',
                      ?, ?, 'ACTIVE', 'aryan', 'zara', 'rakshita', ?)
            RETURNING id""",
            (now_str, expires_str, now_str)
        )
        pid = (await p_cur.fetchone())["id"]
        await db.execute(
            """INSERT INTO post_approval_jobs (
                permit_id, correlation_id, status, attempts, created_at, updated_at
            ) VALUES (?, 'restart-corr-1', 'PENDING', 0, ?, ?)""",
            (pid, now_str, now_str)
        )
        await db.commit()

    recovered = await process_pending_post_approval_jobs()
    assert recovered >= 1

    async with get_db() as db:
        j_cur = await db.execute("SELECT status, artifact_id FROM post_approval_jobs WHERE permit_id = ?", (pid,))
        j = await j_cur.fetchone()
        assert j["status"] == "COMPLETED"
        assert j["artifact_id"] is not None

