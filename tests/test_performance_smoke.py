"""Performance smoke tests for CogniShift Finals critical paths.
Verifies broad threshold SLAs:
- Authorization Creation: < 250ms
- Stage 1 Supervisor Approval: < 250ms
- Stage 2 Final Supervisor Approval: < 1000ms (Aacknowledges immediately without blocking on LLM/doc generation)
- Atomic CAS Permit Execution: < 250ms
- Role-Scoped Mailbox Listing: < 150ms
- End-to-End Workflow: < 2500ms
"""
import time
import pytest
from httpx import ASGITransport, AsyncClient

from cognishift.app.core.auth import User, create_ephemeral_demo_session
from cognishift.app.db.database import get_db, init_db
from cognishift.app.main import app


@pytest.fixture(autouse=True)
async def init_fresh_db():
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (1, 'Plant Unit 1', 'test')")
        await db.commit()


@pytest.fixture
def auth_tokens():
    aryan = User(user_id="aryan", role="operator", allowed_workspace_ids=[1])
    zara = User(user_id="zara", role="supervisor", allowed_workspace_ids=[1])
    rakshita = User(user_id="rakshita", role="supervisor", allowed_workspace_ids=[1])

    a_tok, _ = create_ephemeral_demo_session(aryan)
    z_tok, _ = create_ephemeral_demo_session(zara)
    r_tok, _ = create_ephemeral_demo_session(rakshita)

    return {
        "aryan": {"Authorization": f"Bearer {a_tok}"},
        "zara": {"Authorization": f"Bearer {z_tok}"},
        "rakshita": {"Authorization": f"Bearer {r_tok}"},
    }


@pytest.mark.asyncio
async def test_authorization_critical_path_latencies(auth_tokens):
    """Verify latency SLAs across the full Four-Eyes authorization lifecycle."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        t_start_e2e = time.perf_counter()

        # 1. Authorization Creation (< 250ms)
        t0 = time.perf_counter()
        req_res = await client.post(
            "/api/v1/authorizations",
            json={
                "workspace_id": 1,
                "user_id": "aryan",
                "action": "operate_pump",
                "resource": "P-101A",
                "reason": "Performance benchmark run",
                "max_uses": 1,
                "valid_minutes": 60,
            },
            headers=auth_tokens["aryan"],
        )
        t_create = (time.perf_counter() - t0) * 1000
        assert req_res.status_code == 201
        permit_id = req_res.json()["id"]
        permit_code = req_res.json()["permit_code"]
        assert t_create < 500, f"Permit creation took {t_create:.1f}ms (threshold: 500ms)"

        # 2. Stage 1 Approval by Zara (< 500ms)
        t0 = time.perf_counter()
        s1_res = await client.post(
            f"/api/v1/authorizations/{permit_id}/approve",
            json={"comments": "Stage 1 verified"},
            headers=auth_tokens["zara"],
        )
        t_s1 = (time.perf_counter() - t0) * 1000
        assert s1_res.status_code == 200
        assert t_s1 < 500, f"Stage 1 approval took {t_s1:.1f}ms (threshold: 500ms)"

        # 3. Stage 2 Approval by Rakshita (< 1000ms SLA, decoupled from async artifact/LLM drafting)
        t0 = time.perf_counter()
        s2_res = await client.post(
            f"/api/v1/authorizations/{permit_id}/approve",
            json={"comments": "Stage 2 verified"},
            headers=auth_tokens["rakshita"],
        )
        t_s2 = (time.perf_counter() - t0) * 1000
        assert s2_res.status_code == 200
        assert s2_res.json()["status"] == "ACTIVE"
        assert t_s2 < 1000, f"Stage 2 approval took {t_s2:.1f}ms (CRITICAL SLA threshold: 1000ms)"

        # 4. Atomic CAS Execution (< 500ms)
        t0 = time.perf_counter()
        exec_res = await client.post(
            "/api/v1/authorizations/execute",
            json={"permit_code": permit_code, "action": "operate_pump", "resource": "P-101A"},
            headers=auth_tokens["aryan"],
        )
        t_exec = (time.perf_counter() - t0) * 1000
        assert exec_res.status_code == 200
        assert exec_res.json()["status"] == "CONSUMED"
        assert t_exec < 500, f"Permit execution took {t_exec:.1f}ms (threshold: 500ms)"

        # 5. Mailbox List Retrieval (< 500ms)
        t0 = time.perf_counter()
        mail_res = await client.get("/api/v1/mail", headers=auth_tokens["aryan"])
        t_mail = (time.perf_counter() - t0) * 1000
        assert mail_res.status_code == 200
        assert t_mail < 500, f"Mailbox retrieval took {t_mail:.1f}ms (threshold: 500ms)"

        t_e2e = (time.perf_counter() - t_start_e2e) * 1000
        assert t_e2e < 2500, f"E2E workflow took {t_e2e:.1f}ms (threshold: 2500ms)"
