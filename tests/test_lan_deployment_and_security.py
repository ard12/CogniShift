"""
Comprehensive test suite for LAN deployment, multi-terminal isolation,
cryptographic trusted-device enforcement, and security hardening.
"""
import base64
import json
import time
import pytest
import pandas as pd
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.hashes import SHA256

from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from cognishift.app.core.device_security import (
    begin_challenge,
    verify_challenge,
    validate_device_session,
    approve_device,
    revoke_device,
    block_device,
    restore_active_device_sessions,
    canonical_public_jwk,
    key_fingerprint,
    DEVICE_SESSIONS,
)
from cognishift.app.core.auth import hash_token, get_current_user, User
from cognishift.core.visualization.schemas import ArtifactRequestContract, ChartType, VisualizationSpec
from cognishift.core.visualization.selector import _generate_secondary_spec
from cognishift.core.sandbox.backend import get_sandbox_backend
from cognishift.core.sandbox.schemas import SandboxUnavailableError


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _generate_test_key():
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    numbers = pub.public_numbers()
    jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64url(numbers.x.to_bytes(32, "big")),
        "y": _b64url(numbers.y.to_bytes(32, "big")),
    }
    return priv, jwk


@pytest.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_lan.db"
    monkeypatch.setattr(settings, "database_path", test_db)
    monkeypatch.setattr(settings, "trusted_device_required", True)
    DEVICE_SESSIONS.clear()
    await init_db()
    yield


@pytest.mark.asyncio
async def test_remote_first_admin_bootstrap_denied():
    """Verify that remote network client cannot bootstrap first admin (loopback required)."""
    priv, jwk = _generate_test_key()
    res = await begin_challenge(
        user_id="attacker_admin",
        role="administrator",
        device_id="remote-dev-1",
        display_name="Remote Attacker",
        public_jwk=jwk,
        is_loopback=False,
        client_ip="10.10.199.50",
    )
    # Must fail closed as unknown_device
    assert res["status"] == "unknown_device"

    # Verify device record is pending, not approved
    async with get_db() as db:
        row = await (await db.execute("SELECT * FROM trusted_devices WHERE device_id='remote-dev-1'")).fetchone()
        assert row is not None
        assert row["status"] == "pending"
        assert row["approved_by"] is None


@pytest.mark.asyncio
async def test_loopback_first_admin_bootstrap_succeeds():
    """Verify that loopback client can bootstrap the first administrator."""
    priv, jwk = _generate_test_key()
    res = await begin_challenge(
        user_id="sitanshu",
        role="administrator",
        device_id="sitanshu-host",
        display_name="Sitanshu Laptop",
        public_jwk=jwk,
        is_loopback=True,
        client_ip="127.0.0.1",
    )
    assert res["status"] == "challenge"
    assert "challenge_id" in res
    assert "challenge" in res

    # Verify approved in database
    async with get_db() as db:
        row = await (await db.execute("SELECT * FROM trusted_devices WHERE device_id='sitanshu-host'")).fetchone()
        assert row is not None
        assert row["status"] == "approved"
        assert row["approved_by"] == "sitanshu"


@pytest.mark.asyncio
async def test_multi_user_device_sharing_unique_constraint():
    """Verify that a single browser device_id can be registered across distinct users without collision."""
    priv, jwk = _generate_test_key()
    # User 1 registers device
    res1 = await begin_challenge("user_a", "operator", "shared-browser-1", "Chrome", jwk, is_loopback=False, client_ip="10.10.163.208")
    assert res1["status"] == "unknown_device"

    # User 2 registers SAME device_id
    res2 = await begin_challenge("user_b", "operator", "shared-browser-1", "Chrome", jwk, is_loopback=False, client_ip="10.10.163.208")
    assert res2["status"] == "unknown_device"

    async with get_db() as db:
        rows = await (await db.execute("SELECT user_id, device_id, status FROM trusted_devices WHERE device_id='shared-browser-1'")).fetchall()
        assert len(rows) == 2
        user_ids = {r["user_id"] for r in rows}
        assert user_ids == {"user_a", "user_b"}


@pytest.mark.asyncio
async def test_challenge_verify_session_lifecycle_and_revocation():
    """Verify challenge verify, active session caching, and immediate invalidation on revocation."""
    priv, jwk = _generate_test_key()
    # Bootstrap admin
    await begin_challenge("admin", "administrator", "dev-admin", "Admin PC", jwk, is_loopback=True, client_ip="127.0.0.1")

    # Issue challenge
    c_res = await begin_challenge("admin", "administrator", "dev-admin", "Admin PC", jwk, is_loopback=True, client_ip="127.0.0.1")
    assert c_res["status"] == "challenge"

    challenge_bytes = base64.urlsafe_b64decode(c_res["challenge"] + "==")
    sig_der = priv.sign(challenge_bytes, ec.ECDSA(SHA256()))

    # Complete challenge
    raw_session = await verify_challenge("admin", "dev-admin", c_res["challenge_id"], _b64url(sig_der))
    assert raw_session is not None

    # Validate session
    validated_dev = validate_device_session(raw_session, "admin")
    assert validated_dev == "dev-admin"

    # Wrong user fails validation
    assert validate_device_session(raw_session, "other_user") is None

    # Replay of challenge fails
    with pytest.raises(ValueError, match="invalid or expired"):
        await verify_challenge("admin", "dev-admin", c_res["challenge_id"], _b64url(sig_der))

    # Revoke device immediately terminates session
    await revoke_device("dev-admin", user_id="admin", actor_id="admin")
    assert validate_device_session(raw_session, "admin") is None

    # Verify in DB
    async with get_db() as db:
        active_sess = await (await db.execute("SELECT count(*) as n FROM active_device_sessions WHERE device_id='dev-admin'")).fetchone()
        assert active_sess["n"] == 0
        dev_row = await (await db.execute("SELECT status FROM trusted_devices WHERE device_id='dev-admin'")).fetchone()
        assert dev_row["status"] == "revoked"


@pytest.mark.asyncio
async def test_blocked_device_denies_new_challenges():
    """Verify that blocking a device prevents issuing new challenges."""
    priv, jwk = _generate_test_key()
    await begin_challenge("user_c", "operator", "dev-blocked", "PC", jwk, is_loopback=False, client_ip="10.10.145.22")
    await block_device("dev-blocked", actor_id="admin")

    res = await begin_challenge("user_c", "operator", "dev-blocked", "PC", jwk, is_loopback=False, client_ip="10.10.145.22")
    assert res["status"] == "blocked"


def test_visualization_fake_reversed_fallback_eliminated(tmp_path):
    """Verify that _generate_secondary_spec returns None instead of reversing primary data."""
    df = pd.DataFrame({
        "Tag": ["PT-101", "PT-102", "PT-103"],
        "Pressure": [10.5, 12.3, 14.1],
    })
    dummy_file = tmp_path / "test.csv"
    dummy_file.write_text("Tag,Pressure\nPT-101,10.5\nPT-102,12.3\nPT-103,14.1")

    primary = VisualizationSpec(
        title="Pressure by Tag",
        source_file=dummy_file.name,
        source_sheet=None,
        chart_type=ChartType.BAR,
        x_column="Tag",
        y_columns=["Pressure"],
        x_values=["PT-101", "PT-102", "PT-103"],
        series={"Pressure": [10.5, 12.3, 14.1]},
        x_label="Tag",
        y_label="Pressure",
        output_filename="test_primary.png",
        provenance={"test": True}
    )

    contract = ArtifactRequestContract(png_count=2, requested_chart_types=["bar", "line"])
    # clean_cols has no other candidate columns matching priority, plant_section, total_cost, etc.
    sec = _generate_secondary_spec(
        df=df,
        clean_cols=["Tag", "Pressure"],
        file_path=dummy_file,
        sheet_name=None,
        contract=contract,
        query="show me two charts",
        primary_spec=primary,
    )
    # Must be None, NEVER reversed fake data!
    assert sec is None


def test_sandbox_strict_fail_closed_when_not_simulated(monkeypatch):
    """Verify that get_sandbox_backend raises SandboxUnavailableError if runtime missing and not simulated."""
    monkeypatch.setattr(settings, "operating_mode", "local")
    monkeypatch.setattr(settings, "sandbox_runtime", "nonexistent_docker_bin_xyz123")

    with pytest.raises(SandboxUnavailableError):
        get_sandbox_backend()


@pytest.mark.asyncio
async def test_query_token_rejected_in_get_current_user():
    """Verify that query parameter ?token= is rejected and raises HTTP 401."""
    from unittest.mock import Mock
    from fastapi import Request, HTTPException

    req = Mock(spec=Request)
    req.headers = {}
    req.query_params = {"token": "some_token_in_query"}

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(req)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_restore_active_device_sessions_on_startup():
    """Verify that restore_active_device_sessions restores unexpired sessions into memory cache."""
    import hashlib
    session_raw = "test_restore_session_token_123"
    s_hash = hashlib.sha256(session_raw.encode()).hexdigest()
    expires_at = time.time() + 3600

    async with get_db() as db:
        await db.execute(
            "INSERT INTO active_device_sessions (session_hash, user_id, device_id, key_fingerprint, expires_at) "
            "VALUES (?, 'user_d', 'dev-restored', 'fp123', ?)",
            (s_hash, expires_at),
        )
        await db.commit()

    DEVICE_SESSIONS.clear()
    assert validate_device_session(session_raw, "user_d") is None

    await restore_active_device_sessions()
    assert validate_device_session(session_raw, "user_d") == "dev-restored"

