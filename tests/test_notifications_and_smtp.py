"""Comprehensive test suite for sovereign notifications, local loopback SMTP, and SOC mailbox."""
import asyncio
import base64
import json
import secrets
import pytest
from httpx import AsyncClient, ASGITransport

from cognishift.app.main import app
from cognishift.app.db.database import get_db, init_db
from cognishift.core.notifications import (
    CitationClass,
    NotificationCitation,
    NotificationEvidencePack,
    NotificationType,
    Severity,
    check_smtp_health,
    collect_artifact_evidence,
    collect_four_eyes_evidence,
    collect_network_drift_evidence,
    collect_untrusted_device_evidence,
    compose_notification,
    dispatch_notification_for_event,
    evaluate_routing_policy,
    send_internal_email,
    start_local_smtp_server,
    stop_local_smtp_server,
    validate_citation,
    validate_citations,
)
from cognishift.app.core.device_security import begin_challenge, key_fingerprint


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def cleanup_smtp():
    yield
    await stop_local_smtp_server()


@pytest.mark.asyncio
async def test_smtp_server_loopback_restriction():
    """Verify that SMTP listener strictly rejects binding to non-loopback addresses."""
    with pytest.raises(ValueError, match="CRITICAL SECURITY VIOLATION"):
        await start_local_smtp_server(host="0.0.0.0", port=10999)


@pytest.mark.asyncio
async def test_smtp_server_handshake_and_dispatch():
    """Verify local loopback SMTP server accepts RFC 5321 handshake and email delivery."""
    server = await start_local_smtp_server(host="127.0.0.1", port=1025)
    assert server is not None

    health = await check_smtp_health(host="127.0.0.1", port=1025)
    assert health["status"] == "ACTIVE"
    assert health["loopback_only"] is True

    # Send test message
    sent = await send_internal_email(
        sender="security-bot@secure.internal",
        recipients=["admin@secure.internal"],
        subject="[TEST] Sovereign Loopback Delivery Verification",
        body_text="Test delivery body over 127.0.0.1:1025",
        host="127.0.0.1",
        port=1025,
    )
    assert sent is True


@pytest.mark.asyncio
async def test_evidence_pack_collection():
    """Verify deterministic evidence collection functions populate verified fields."""
    untrusted = collect_untrusted_device_evidence(
        user_id="rohit",
        device_id="dev-rohit-xyz",
        key_fingerprint="sha256-fingerprint-1234",
        client_ip="10.10.145.22",
        audit_event_id=99,
    )
    assert untrusted.event_type == NotificationType.UNTRUSTED_DEVICE
    assert untrusted.severity == Severity.HIGH
    assert untrusted.target_user == "rohit"
    assert untrusted.client_ip == "10.10.145.22"
    assert len(untrusted.citations) == 2

    drift = collect_network_drift_evidence(
        user_id="vicky",
        device_id="dev-vicky-abc",
        key_fingerprint="sha256-vicky-987",
        client_ip="10.10.164.99",
        previous_ip="10.10.164.63",
        is_foreign=False,
    )
    assert drift.event_type == NotificationType.NETWORK_DRIFT
    assert drift.severity == Severity.MEDIUM
    assert drift.previous_ip == "10.10.164.63"

    four_eyes = collect_four_eyes_evidence(
        event_type=NotificationType.SENSITIVE_ACTION_REQUESTED,
        run_id=101,
        approval_id=5,
        tool_name="restart_component",
        parameters={"component_id": "P-101A"},
        user_id="operator",
        workspace_id=1,
    )
    assert four_eyes.event_type == NotificationType.SENSITIVE_ACTION_REQUESTED
    assert four_eyes.severity == Severity.HIGH
    assert four_eyes.run_id == 101

    art = collect_artifact_evidence(
        run_id=102,
        workspace_id=1,
        user_id="operator",
        artifact_id=10,
        artifact_name="safety_permit.docx",
        artifact_path="safety/safety_permit.docx",
    )
    assert art.event_type == NotificationType.ARTIFACT_COMPLETED
    assert art.severity == Severity.LOW


def test_deterministic_routing_policy():
    """Verify routing policy maps events strictly to deterministic recipients."""
    ev_admin = NotificationEvidencePack(
        event_type=NotificationType.UNTRUSTED_DEVICE,
        severity=Severity.HIGH,
    )
    sender, recips = evaluate_routing_policy(ev_admin)
    assert sender == "security-bot@secure.internal"
    assert recips == ["admin@secure.internal"]

    ev_fe = NotificationEvidencePack(
        event_type=NotificationType.SENSITIVE_ACTION_REQUESTED,
        severity=Severity.HIGH,
    )
    sender, recips = evaluate_routing_policy(ev_fe)
    assert sender == "governance-bot@secure.internal"
    assert "zara@secure.internal" in recips
    assert "rakshita@secure.internal" in recips

    ev_stage1 = NotificationEvidencePack(
        event_type=NotificationType.FIRST_SUPERVISOR_APPROVAL,
        severity=Severity.MEDIUM,
        supervisor_1="zara",
    )
    _, recips = evaluate_routing_policy(ev_stage1)
    assert recips == ["rakshita@secure.internal"]


@pytest.mark.asyncio
async def test_fail_closed_citation_validation():
    """Verify validator accepts existing DB records and flags non-existent ones."""
    await init_db()
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO audit_events (action, resource_type, details, result) VALUES ('test_action', 'test', 'det', 'ok')"
        )
        valid_audit_id = cur.lastrowid
        await db.commit()

    cit_valid = NotificationCitation(
        citation_index=1,
        citation_type=CitationClass.AUDIT,
        display_label="Valid Audit Event",
        source_id=str(valid_audit_id),
    )
    cit_fake = NotificationCitation(
        citation_index=2,
        citation_type=CitationClass.AUDIT,
        display_label="Fabricated Audit Event",
        source_id="99999999",
    )

    assert await validate_citation(cit_valid) is True
    assert await validate_citation(cit_fake) is False

    validated_list, all_valid = await validate_citations([cit_valid, cit_fake], strip_invalid=True)
    assert all_valid is False
    assert len(validated_list) == 1
    assert validated_list[0].source_id == str(valid_audit_id)


@pytest.mark.asyncio
async def test_composer_deterministic_fallback():
    """Verify composer produces structured plain text and HTML in fallback mode."""
    ev = NotificationEvidencePack(
        event_type=NotificationType.UNTRUSTED_DEVICE,
        severity=Severity.HIGH,
        target_user="rohit",
        client_ip="10.10.145.22",
        device_id="dev-rohit-test",
        device_fingerprint="sha256-fingerprint-test",
        summary="Unregistered ECDSA key from Rohit intercepted.",
    )
    composed = await compose_notification(
        evidence=ev,
        sender="security-bot@secure.internal",
        recipients=["admin@secure.internal"],
    )

    assert "[COGNISHIFT - HIGH]" in composed.subject
    assert "rohit" in composed.body_text
    assert "10.10.145.22" in composed.body_text
    assert "127.0.0.1:1025" in composed.body_text
    assert "<html>" in composed.body_html.lower()


@pytest.mark.asyncio
async def test_dispatch_notification_end_to_end():
    """Verify end-to-end dispatch stores alert, citations, and outbox queue."""
    await init_db()
    await start_local_smtp_server()

    ev = NotificationEvidencePack(
        event_type=NotificationType.TEST_ALERT,
        severity=Severity.LOW,
        target_user="sitanshu",
        client_ip="127.0.0.1",
        summary="End-to-end integration test alert.",
        citations=[
            NotificationCitation(
                citation_index=1,
                citation_type=CitationClass.DEVICE,
                display_label="Loopback Interface",
                source_id="sitanshu",
            )
        ],
    )

    alert_id, composed, delivered = await dispatch_notification_for_event(ev, dedup_window_seconds=1)
    assert alert_id > 0
    assert delivered is True

    async with get_db() as db:
        row = await (await db.execute("SELECT * FROM offline_security_alerts WHERE id = ?", (alert_id,))).fetchone()
        assert row is not None
        assert row["alert_type"] == "TEST_ALERT"
        assert row["related_user"] == "sitanshu"

        cits = await (await db.execute("SELECT * FROM notification_citations WHERE alert_id = ?", (alert_id,))).fetchall()
        assert len(cits) == 1


@pytest.mark.asyncio
async def test_device_security_untrusted_attempt_triggers_alert():
    """Verify an unknown device connecting via begin_challenge triggers an UNTRUSTED_DEVICE alert."""
    await init_db()
    await start_local_smtp_server()

    unknown_jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("="),
        "y": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("="),
    }

    dev_id = f"test-dev-{secrets.token_hex(4)}"
    res = await begin_challenge(
        user_id="rohit",
        role="operator",
        device_id=dev_id,
        display_name="Rohit Unknown Laptop",
        public_jwk=unknown_jwk,
        is_loopback=False,
        client_ip="10.10.145.22",
    )
    assert res["status"] == "unknown_device"

    # Allow fire-and-forget background task to finish
    await asyncio.sleep(0.3)

    async with get_db() as db:
        alert = await (await db.execute(
            "SELECT * FROM offline_security_alerts WHERE related_user = 'rohit' AND alert_type = 'UNTRUSTED_DEVICE' ORDER BY id DESC LIMIT 1"
        )).fetchone()
        assert alert is not None
        assert alert["related_ip"] == "10.10.145.22"
        assert alert["severity"] == "HIGH"
        # Clean up the pending test device so it doesn't leak into subsequent test suites
        await db.execute("DELETE FROM trusted_devices WHERE device_id = ?", (dev_id,))
        await db.commit()


@pytest.mark.asyncio
async def test_device_network_drift_telemetry_and_alert():
    """Verify an approved device with IP drift records telemetry and NETWORK_DRIFT notification."""
    await init_db()
    await start_local_smtp_server()

    approved_jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("="),
        "y": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("="),
    }
    fp = key_fingerprint(approved_jwk)
    dev_id = f"test-vicky-{secrets.token_hex(4)}"

    async with get_db() as db:
        await db.execute(
            "INSERT INTO trusted_devices (device_id, user_id, display_name, public_key_jwk, key_fingerprint, status, last_ip) "
            "VALUES (?, 'vicky', 'Vicky Laptop', ?, ?, 'approved', '10.10.164.63')",
            (dev_id, json.dumps(approved_jwk), fp),
        )
        await db.commit()

    # Reconnect on a different IP within the same subnet (10.10.164.88)
    res = await begin_challenge(
        user_id="vicky",
        role="operator",
        device_id=dev_id,
        display_name="Vicky Laptop",
        public_jwk=approved_jwk,
        is_loopback=False,
        client_ip="10.10.164.88",
    )
    assert res["status"] == "challenge"

    await asyncio.sleep(0.3)

    async with get_db() as db:
        # Check telemetry updated in trusted_devices table
        dev_row = await (await db.execute(
            "SELECT last_ip, previous_ip FROM trusted_devices WHERE device_id = ?",
            (dev_id,),
        )).fetchone()
        assert dev_row["last_ip"] == "10.10.164.88"
        assert dev_row["previous_ip"] == "10.10.164.63"

        # Check audit event
        audit = await (await db.execute(
            "SELECT * FROM audit_events WHERE action = 'DEVICE_NETWORK_DRIFT' ORDER BY id DESC LIMIT 1"
        )).fetchone()
        assert audit is not None
        assert "Trusted device observed from a new network address" in audit["details"]

        # Clean up test device
        await db.execute("DELETE FROM trusted_devices WHERE device_id = ?", (dev_id,))
        await db.commit()


@pytest.mark.asyncio
async def test_security_dashboard_api_mailbox_and_health():
    """Verify security dashboard REST endpoints for mailbox and SMTP health."""
    await init_db()
    await start_local_smtp_server()

    # Create admin auth headers
    from cognishift.app.core.auth import User, create_ephemeral_demo_session
    admin_token, _ = create_ephemeral_demo_session(User(user_id="sitanshu", role="administrator", allowed_workspace_ids=[1]))
    headers = {"Authorization": f"Bearer {admin_token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        health_res = await client.get("/api/v1/security/alerts/smtp-health", headers=headers)
        assert health_res.status_code == 200
        assert health_res.json()["status"] == "ACTIVE"

        # 2. Dispatch test alert via API
        disp_res = await client.post("/api/v1/security/alerts/dispatch-test", headers=headers)
        assert disp_res.status_code == 200
        disp_data = disp_res.json()
        assert disp_data["status"] == "dispatched"
        alert_id = disp_data["alert_id"]

        # 3. Read mailbox
        mb_res = await client.get("/api/v1/security/alerts/mailbox", headers=headers)
        assert mb_res.status_code == 200
        mb_data = mb_res.json()
        assert mb_data["total_count"] >= 1
        assert any(a["id"] == alert_id for a in mb_data["alerts"])

        # 4. Read single alert detail
        det_res = await client.get(f"/api/v1/security/alerts/{alert_id}", headers=headers)
        assert det_res.status_code == 200
        det_data = det_res.json()
        assert det_data["id"] == alert_id
        assert "citations" in det_data

        # 5. Mark alert as read
        read_res = await client.post(f"/api/v1/security/alerts/{alert_id}/read", headers=headers)
        assert read_res.status_code == 200
        assert read_res.json()["is_read"] == 1
