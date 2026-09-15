"""Comprehensive QA verification of Device Security Lifecycle and IP Drift Telemetry.

Covers tests A through I:
- Test A: First Admin loopback bootstrap vs remote bootstrap denial
- Test B: Unknown ECDSA key + valid credentials -> 403 UNKNOWN_DEVICE
- Test C: Admin approves device -> challenge signed -> session issued
- Test D: Replay of consumed challenge -> rejected
- Test E: Wrong ECDSA key against approved device ID -> rejected
- Test F: Admin revokes device -> database & in-memory session evicted immediately -> request rejected
- Test G: Blocked device denied new challenge/session
- Test H: Restart application -> persisted active sessions restored cleanly
- Test I: ?token=... in query parameter rejected (header-only auth)
- IP Drift Battery: same-subnet drift vs foreign network vs unknown key
"""
import base64
import time
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import status
from httpx import ASGITransport, AsyncClient

from cognishift.app.config import settings
from cognishift.app.core.device_security import (
    DEVICE_SESSIONS,
    restore_active_device_sessions,
)
from cognishift.app.db.database import get_db
from cognishift.app.main import app

TEST_ADMIN_TOKEN = "test-token-admin-112"
TEST_OPERATOR_TOKEN = "test-token-operator-998"


def enc(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def generate_identity(device_id: str, display_name: str = "QA Terminal"):
    key = ec.generate_private_key(ec.SECP256R1())
    numbers = key.public_key().public_numbers()
    jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": enc(numbers.x.to_bytes(32, "big")),
        "y": enc(numbers.y.to_bytes(32, "big")),
    }
    return key, {"device_id": device_id, "display_name": display_name, "public_key_jwk": jwk}


async def solve_challenge(client: AsyncClient, token: str, key, payload: dict):
    res = await client.post(
        "/api/v1/auth/device/challenge",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if res.status_code != 200:
        return res, None

    body = res.json()
    raw_chal = base64.urlsafe_b64decode(body["challenge"] + "=" * (-len(body["challenge"]) % 4))
    sig = key.sign(raw_chal, ec.ECDSA(hashes.SHA256()))
    verify_res = await client.post(
        "/api/v1/auth/device/verify",
        json={
            "device_id": payload["device_id"],
            "challenge_id": body["challenge_id"],
            "signature": enc(sig),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    if verify_res.status_code != 200:
        return verify_res, None
    return verify_res, verify_res.json()["device_session"]


@pytest.fixture(autouse=True)
async def clean_device_tables():
    """Ensure clean slate for device security tables before and after each test."""
    async with get_db() as db:
        await db.execute("DELETE FROM active_device_sessions")
        await db.execute("DELETE FROM device_challenges")
        await db.execute("DELETE FROM trusted_devices")
        await db.commit()
    DEVICE_SESSIONS.clear()
    yield
    async with get_db() as db:
        await db.execute("DELETE FROM active_device_sessions")
        await db.execute("DELETE FROM device_challenges")
        await db.execute("DELETE FROM trusted_devices")
        await db.commit()
    DEVICE_SESSIONS.clear()


@pytest.mark.asyncio
async def test_a_first_admin_loopback_bootstrap_vs_remote_denial(monkeypatch):
    monkeypatch.setattr(settings, "trusted_device_required", True)

    # 1. Admin connecting from remote IP (10.10.145.22) -> DENIED bootstrap
    remote_transport = ASGITransport(app=app, client=("10.10.145.22", 51234))
    async with AsyncClient(transport=remote_transport, base_url="http://test") as remote_client:
        admin_key, admin_id = generate_identity("remote-admin-dev")
        resp = await remote_client.post(
            "/api/v1/auth/device/challenge",
            json=admin_id,
            headers={"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.json()["detail"]["code"] == "UNKNOWN_DEVICE"

        # Verify audit log reflects remote bootstrap denial
        async with get_db() as db:
            row = await (await db.execute(
                "SELECT details, result FROM audit_events WHERE action='device_verification_failed' ORDER BY id DESC LIMIT 1"
            )).fetchone()
            assert "Remote administrator bootstrap denied without loopback" in row["details"]
            assert row["result"] == "blocked"

    # 2. Admin connecting from loopback (127.0.0.1) -> ALLOWED bootstrap
    loopback_transport = ASGITransport(app=app, client=("127.0.0.1", 51235))
    async with AsyncClient(transport=loopback_transport, base_url="http://test") as local_client:
        local_admin_key, local_admin_id = generate_identity("local-admin-dev")
        verify_resp, session = await solve_challenge(local_client, TEST_ADMIN_TOKEN, local_admin_key, local_admin_id)
        assert verify_resp.status_code == 200
        assert session is not None

        # Verify admin can now access protected /me endpoint
        me_resp = await local_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {TEST_ADMIN_TOKEN}", "X-Device-Session": session},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["user_id"] == "admin_rohit"


@pytest.mark.asyncio
async def test_b_c_d_e_f_g_device_lifecycle_and_security_controls(monkeypatch):
    monkeypatch.setattr(settings, "trusted_device_required", True)

    loopback_transport = ASGITransport(app=app, client=("127.0.0.1", 51234))
    async with AsyncClient(transport=loopback_transport, base_url="http://test") as client:
        # Bootstrap Admin
        adm_key, adm_id = generate_identity("admin-root-dev")
        _, adm_session = await solve_challenge(client, TEST_ADMIN_TOKEN, adm_key, adm_id)
        adm_headers = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}", "X-Device-Session": adm_session}

        # --- TEST B: Unknown ECDSA key + valid operator credentials -> 403 UNKNOWN_DEVICE ---
        op_key, op_id = generate_identity("operator-workstation-01")
        unknown_resp = await client.post(
            "/api/v1/auth/device/challenge",
            json=op_id,
            headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"},
        )
        assert unknown_resp.status_code == status.HTTP_403_FORBIDDEN
        assert unknown_resp.json()["detail"]["code"] == "UNKNOWN_DEVICE"
        assert unknown_resp.json()["detail"]["credentials"] == "Credentials Verified"

        # Direct access without device session also fails
        blocked_me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"})
        assert blocked_me.status_code == status.HTTP_403_FORBIDDEN
        assert blocked_me.json()["detail"]["code"] == "UNKNOWN_DEVICE"

        # --- TEST C: Admin approves device -> challenge signed -> session issued ---
        pending = await client.get("/api/v1/security/devices/pending", headers=adm_headers)
        assert pending.status_code == 200
        pending_devs = [d["device_id"] for d in pending.json()]
        assert "operator-workstation-01" in pending_devs

        approve_resp = await client.post(
            f"/api/v1/security/devices/{op_id['device_id']}/approve",
            headers=adm_headers,
        )
        assert approve_resp.status_code == 200

        # Now operator can solve challenge and get a valid session
        chal_resp = await client.post(
            "/api/v1/auth/device/challenge",
            json=op_id,
            headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"},
        )
        assert chal_resp.status_code == 200
        chal_data = chal_resp.json()
        chal_bytes = base64.urlsafe_b64decode(chal_data["challenge"] + "=" * (-len(chal_data["challenge"]) % 4))
        op_sig = op_key.sign(chal_bytes, ec.ECDSA(hashes.SHA256()))

        verify_resp = await client.post(
            "/api/v1/auth/device/verify",
            json={
                "device_id": op_id["device_id"],
                "challenge_id": chal_data["challenge_id"],
                "signature": enc(op_sig),
            },
            headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"},
        )
        assert verify_resp.status_code == 200
        op_session = verify_resp.json()["device_session"]
        op_headers = {"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}", "X-Device-Session": op_session}

        # Protected endpoint succeeds with approved session
        me_ok = await client.get("/api/v1/auth/me", headers=op_headers)
        assert me_ok.status_code == 200

        # --- TEST D: Replay of consumed challenge -> rejected ---
        replay_resp = await client.post(
            "/api/v1/auth/device/verify",
            json={
                "device_id": op_id["device_id"],
                "challenge_id": chal_data["challenge_id"],
                "signature": enc(op_sig),
            },
            headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"},
        )
        assert replay_resp.status_code == status.HTTP_403_FORBIDDEN
        assert "invalid or expired" in replay_resp.json()["detail"].lower()

        # --- TEST E: Wrong ECDSA key against approved device ID -> rejected ---
        chal_resp2 = await client.post(
            "/api/v1/auth/device/challenge",
            json=op_id,
            headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"},
        )
        assert chal_resp2.status_code == 200
        chal_data2 = chal_resp2.json()
        chal_bytes2 = base64.urlsafe_b64decode(chal_data2["challenge"] + "=" * (-len(chal_data2["challenge"]) % 4))

        # Sign with attacker key
        attacker_key, _ = generate_identity("attacker-dev")
        attacker_sig = attacker_key.sign(chal_bytes2, ec.ECDSA(hashes.SHA256()))

        bad_verify = await client.post(
            "/api/v1/auth/device/verify",
            json={
                "device_id": op_id["device_id"],
                "challenge_id": chal_data2["challenge_id"],
                "signature": enc(attacker_sig),
            },
            headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"},
        )
        assert bad_verify.status_code == status.HTTP_403_FORBIDDEN
        assert "signature verification failed" in bad_verify.json()["detail"].lower()

        # --- TEST F: Admin revokes device -> database & in-memory session evicted immediately ---
        revoke_resp = await client.post(
            f"/api/v1/security/devices/{op_id['device_id']}/revoke",
            headers=adm_headers,
        )
        assert revoke_resp.status_code == 200

        # Operator session is evicted immediately: access fails with 403
        revoked_access = await client.get("/api/v1/auth/me", headers=op_headers)
        assert revoked_access.status_code == status.HTTP_403_FORBIDDEN
        assert revoked_access.json()["detail"]["code"] == "UNKNOWN_DEVICE"

        # --- TEST G: Blocked device denied new challenge/session ---
        block_resp = await client.post(
            f"/api/v1/security/devices/{op_id['device_id']}/block",
            headers=adm_headers,
        )
        assert block_resp.status_code == 200

        blocked_chal = await client.post(
            "/api/v1/auth/device/challenge",
            json=op_id,
            headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"},
        )
        assert blocked_chal.status_code == status.HTTP_403_FORBIDDEN
        assert blocked_chal.json()["detail"]["device_status"] == "blocked"


@pytest.mark.asyncio
async def test_h_restart_durability_and_active_session_restoration(monkeypatch):
    """Test H: Restart application -> persisted active sessions restored cleanly from SQLite."""
    monkeypatch.setattr(settings, "trusted_device_required", True)

    transport = ASGITransport(app=app, client=("127.0.0.1", 51236))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        adm_key, adm_id = generate_identity("durable-admin")
        _, session = await solve_challenge(client, TEST_ADMIN_TOKEN, adm_key, adm_id)
        headers = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}", "X-Device-Session": session}

        # Verify access is working initially
        resp = await client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200

        # Simulate abrupt process crash / restart: purge in-memory session cache
        assert len(DEVICE_SESSIONS) > 0
        DEVICE_SESSIONS.clear()
        assert len(DEVICE_SESSIONS) == 0

        # Without restoration, session is missing from RAM
        resp_after_crash = await client.get("/api/v1/auth/me", headers=headers)
        assert resp_after_crash.status_code == status.HTTP_403_FORBIDDEN

        # Simulate startup restoration lifecycle (runs during FastAPI lifespan)
        await restore_active_device_sessions()
        assert len(DEVICE_SESSIONS) > 0

        # Access is restored cleanly
        resp_restored = await client.get("/api/v1/auth/me", headers=headers)
        assert resp_restored.status_code == 200
        assert resp_restored.json()["user_id"] == "admin_rohit"


@pytest.mark.asyncio
async def test_i_query_param_token_rejected_header_only_supported(monkeypatch):
    """Test I: ?token=... or ?session=... in query parameters rejected (header-only supported)."""
    monkeypatch.setattr(settings, "trusted_device_required", False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Pass token in query string without Authorization header
        resp = await client.get(f"/api/v1/auth/me?token={TEST_OPERATOR_TOKEN}")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing authentication credentials" in resp.json()["detail"]

        # Header works
        resp_header = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"},
        )
        assert resp_header.status_code == 200


@pytest.mark.asyncio
async def test_ip_drift_telemetry_matrix(monkeypatch):
    """Verify IP drift telemetry behavior:
    1. Known key + same IP -> challenge issued, no drift log.
    2. Known key + same subnet new IP -> challenge issued, DEVICE_NETWORK_DRIFT logged (no false hijacking claim).
    3. Known key + foreign subnet new IP -> challenge issued, DEVICE_FOREIGN_NETWORK_OBSERVED logged.
    4. Unknown key + team IP -> remains 403 UNKNOWN_DEVICE.
    """
    monkeypatch.setattr(settings, "trusted_device_required", True)

    # 1. Bootstrap admin
    adm_transport = ASGITransport(app=app, client=("127.0.0.1", 50001))
    async with AsyncClient(transport=adm_transport, base_url="http://test") as adm_client:
        adm_key, adm_id = generate_identity("drift-admin")
        _, adm_sess = await solve_challenge(adm_client, TEST_ADMIN_TOKEN, adm_key, adm_id)
        adm_headers = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}", "X-Device-Session": adm_sess}

        # 2. Operator initial registration from 10.10.144.10
        op_key, op_id = generate_identity("drift-op-dev")
        t1 = ASGITransport(app=app, client=("10.10.144.10", 50002))
        async with AsyncClient(transport=t1, base_url="http://test") as c1:
            req1 = await c1.post(
                "/api/v1/auth/device/challenge",
                json=op_id,
                headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"},
            )
            assert req1.status_code == status.HTTP_403_FORBIDDEN

        # Admin approves
        await adm_client.post(f"/api/v1/security/devices/{op_id['device_id']}/approve", headers=adm_headers)

        # 3. Same IP (10.10.144.10) -> Challenge issued, NO drift event
        async with AsyncClient(transport=t1, base_url="http://test") as c1:
            chal1 = await c1.post(
                "/api/v1/auth/device/challenge",
                json=op_id,
                headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"},
            )
            assert chal1.status_code == 200

        async with get_db() as db:
            drift_count = await (await db.execute(
                "SELECT COUNT(*) as c FROM audit_events WHERE action IN ('DEVICE_NETWORK_DRIFT', 'DEVICE_FOREIGN_NETWORK_OBSERVED')"
            )).fetchone()
            assert drift_count["c"] == 0

        # 4. Same subnet drift (10.10.144.10 -> 10.10.144.88)
        t2 = ASGITransport(app=app, client=("10.10.144.88", 50003))
        async with AsyncClient(transport=t2, base_url="http://test") as c2:
            chal2 = await c2.post(
                "/api/v1/auth/device/challenge",
                json=op_id,
                headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"},
            )
            assert chal2.status_code == 200

        async with get_db() as db:
            audit = await (await db.execute(
                "SELECT action, details FROM audit_events WHERE action='DEVICE_NETWORK_DRIFT' ORDER BY id DESC LIMIT 1"
            )).fetchone()
            assert audit is not None
            assert "old_ip=10.10.144.10" in audit["details"]
            assert "new_ip=10.10.144.88" in audit["details"]

        # 5. Foreign network drift (10.10.144.88 -> 192.168.1.105)
        t3 = ASGITransport(app=app, client=("192.168.1.105", 50004))
        async with AsyncClient(transport=t3, base_url="http://test") as c3:
            chal3 = await c3.post(
                "/api/v1/auth/device/challenge",
                json=op_id,
                headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"},
            )
            assert chal3.status_code == 200

        async with get_db() as db:
            foreign_audit = await (await db.execute(
                "SELECT action, details FROM audit_events WHERE action='DEVICE_FOREIGN_NETWORK_OBSERVED' ORDER BY id DESC LIMIT 1"
            )).fetchone()
            assert foreign_audit is not None
            assert "old_ip=10.10.144.88" in foreign_audit["details"]
            assert "new_ip=192.168.1.105" in foreign_audit["details"]

        # 6. Unknown key from a team IP (10.10.145.22) -> remains 403 UNKNOWN_DEVICE
        t4 = ASGITransport(app=app, client=("10.10.145.22", 50005))
        async with AsyncClient(transport=t4, base_url="http://test") as c4:
            _, unknown_id = generate_identity("unregistered-device-xyz")
            res_unknown = await c4.post(
                "/api/v1/auth/device/challenge",
                json=unknown_id,
                headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"},
            )
            assert res_unknown.status_code == status.HTTP_403_FORBIDDEN
            assert res_unknown.json()["detail"]["code"] == "UNKNOWN_DEVICE"
