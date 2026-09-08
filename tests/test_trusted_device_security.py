import base64

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import status
from httpx import ASGITransport, AsyncClient

from cognishift.app.config import settings
from cognishift.app.db.database import get_db
from cognishift.app.main import app
TEST_ADMIN_TOKEN = "test-token-admin-112"
TEST_OPERATOR_TOKEN = "test-token-operator-998"


def enc(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def identity(device_id: str):
    key = ec.generate_private_key(ec.SECP256R1())
    numbers = key.public_key().public_numbers()
    jwk = {"kty": "EC", "crv": "P-256", "x": enc(numbers.x.to_bytes(32, "big")), "y": enc(numbers.y.to_bytes(32, "big"))}
    return key, {"device_id": device_id, "display_name": "QA browser", "public_key_jwk": jwk}


async def prove(client: AsyncClient, token: str, key, payload):
    challenge = await client.post("/api/v1/auth/device/challenge", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert challenge.status_code == 200, challenge.text
    body = challenge.json()
    raw = base64.urlsafe_b64decode(body["challenge"] + "=" * (-len(body["challenge"]) % 4))
    signature = key.sign(raw, ec.ECDSA(hashes.SHA256()))
    verified = await client.post("/api/v1/auth/device/verify", json={
        "device_id": payload["device_id"], "challenge_id": body["challenge_id"], "signature": enc(signature),
    }, headers={"Authorization": f"Bearer {token}"})
    assert verified.status_code == 200, verified.text
    return verified.json()["device_session"]


@pytest.mark.asyncio
async def test_unknown_device_block_audit_admin_approval_and_challenge_response(monkeypatch):
    monkeypatch.setattr(settings, "trusted_device_required", True)
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id,name,description) VALUES (1,'Security QA','test')")
        await db.execute("INSERT OR IGNORE INTO tool_definitions (id,name,risk_level,requires_approval,enabled,implementation_key) VALUES (1,'restart_component','sensitive',1,1,'restart_component')")
        await db.commit()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_key, admin_identity = identity("admin-device")
        admin_session = await prove(client, TEST_ADMIN_TOKEN, admin_key, admin_identity)
        admin_headers = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}", "X-Device-Session": admin_session}

        operator_key, operator_identity = identity("unknown-operator-device")
        unknown = await client.post("/api/v1/auth/device/challenge", json=operator_identity, headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"})
        assert unknown.status_code == status.HTTP_403_FORBIDDEN
        assert unknown.json()["detail"]["code"] == "UNKNOWN_DEVICE"
        assert unknown.json()["detail"]["credentials"] == "Credentials Verified"

        blocked = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"})
        assert blocked.status_code == status.HTTP_403_FORBIDDEN
        assert blocked.json()["detail"]["action"] == "Administrator Approval Required"

        pending = await client.get("/api/v1/security/devices/pending", headers=admin_headers)
        assert pending.status_code == 200
        assert pending.json()[0]["device_id"] == operator_identity["device_id"]
        approved = await client.post(f"/api/v1/security/devices/{operator_identity['device_id']}/approve", headers=admin_headers)
        assert approved.status_code == 200

        operator_session = await prove(client, TEST_OPERATOR_TOKEN, operator_key, operator_identity)
        op_headers = {"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}", "X-Device-Session": operator_session}
        me = await client.get("/api/v1/auth/me", headers=op_headers)
        assert me.status_code == 200
        posture = await client.get("/api/v1/security/status?workspace_id=1", headers=op_headers)
        assert posture.status_code == 200
        assert posture.json()["identity"]["status"] == "verified"
        assert posture.json()["device"]["status"] == "trusted"
        assert posture.json()["workspace"]["status"] == "authorized"

        # One physical browser/device key can be registered for multiple users.
        # This is the quick-connect persona-switch regression that previously
        # collided on device_id and surfaced as an unhandled HTTP 500.
        shared_identity = dict(admin_identity)
        shared = await client.post(
            "/api/v1/auth/device/challenge",
            json=shared_identity,
            headers={"Authorization": f"Bearer {TEST_OPERATOR_TOKEN}"},
        )
        assert shared.status_code == status.HTTP_403_FORBIDDEN
        shared_pending = await client.get("/api/v1/security/devices/pending", headers=admin_headers)
        shared_row = next(
            item for item in shared_pending.json()
            if item["device_id"] == shared_identity["device_id"]
        )
        approved_shared = await client.post(
            f"/api/v1/security/devices/{shared_identity['device_id']}/approve",
            params={"user_id": shared_row["user_id"]},
            headers=admin_headers,
        )
        assert approved_shared.status_code == 200, approved_shared.text
        shared_session = await prove(client, TEST_OPERATOR_TOKEN, admin_key, shared_identity)
        shared_me = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {TEST_OPERATOR_TOKEN}",
                "X-Device-Session": shared_session,
            },
        )
        assert shared_me.status_code == 200

    async with get_db() as db:
        row = await (await db.execute("SELECT action,result FROM audit_events WHERE action='device_verification_failed' ORDER BY id DESC LIMIT 1")).fetchone()
        assert row["result"] == "blocked"
