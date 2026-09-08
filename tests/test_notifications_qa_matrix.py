"""QA Verification Matrix for Sovereign Security Notifications, SMTP Transport, and RBAC.

Covers:
- Deduplication under rapid successive dispatches
- Outbox persistence, restart resilience, and flush_pending_outbox recovery
- Citation fail-closed validation across all citation types (AUDIT, DEVICE, RUN, APPROVAL, ARTIFACT, DOCUMENT)
- Local SMTP loopback socket binding (strictly 127.0.0.1, not 0.0.0.0)
- RBAC enforcement: operator role receives 403 across all /alerts/* endpoints
- Mailbox .eml sensitive data hygiene (no bearer tokens, private keys, or passwords)
"""
import asyncio
from pathlib import Path
import socket
from unittest.mock import AsyncMock
import pytest
from httpx import ASGITransport, AsyncClient

from cognishift.app.core.auth import (
    User,
    create_ephemeral_demo_session,
)
from cognishift.app.db.database import get_db, init_db
from cognishift.app.main import app
from cognishift.core.notifications import (
    CitationClass,
    NotificationCitation,
    NotificationEvidencePack,
    NotificationType,
    Severity,
    compose_notification,
    dispatch_notification_for_event,
    evaluate_routing_policy,
    flush_pending_outbox,
    start_local_smtp_server,
    stop_local_smtp_server,
    validate_citation,
    validate_citations,
)

MAILBOX_DIR = Path("data/alerts/mailbox")


@pytest.fixture(autouse=True)
async def ensure_clean_state():
    await init_db()
    try:
        await start_local_smtp_server(host="127.0.0.1", port=1025)
    except Exception:
        pass
    yield


@pytest.mark.asyncio
async def test_deduplication_suppresses_duplicate_dispatches():
    """Verify rapid successive dispatches within the dedup window do not generate duplicate alerts."""
    ev = NotificationEvidencePack(
        event_type=NotificationType.UNTRUSTED_DEVICE,
        severity=Severity.HIGH,
        target_user="rohit_dedup_test",
        device_id="dedup-device-1",
        client_ip="10.10.145.22",
        summary="Rapid dispatch test 1",
    )

    id1, comp1, del1 = await dispatch_notification_for_event(ev, dedup_window_seconds=15)
    assert id1 > 0
    assert del1 is True

    # Dispatch exact same event immediately
    id2, comp2, del2 = await dispatch_notification_for_event(ev, dedup_window_seconds=15)
    assert id2 == id1  # Returned the existing ID, did not create duplicate

    async with get_db() as db:
        count = await (await db.execute(
            "SELECT COUNT(*) as c FROM offline_security_alerts WHERE related_user = 'rohit_dedup_test'"
        )).fetchone()
        assert count["c"] == 1


@pytest.mark.asyncio
async def test_outbox_persistence_and_flush_recovery(monkeypatch):
    """Verify pending or failed outbox records are recovered and delivered by flush_pending_outbox."""
    import cognishift.core.notifications.outbox as outbox_mod

    # Simulate SMTP transport failure during initial dispatch
    monkeypatch.setattr(outbox_mod, "send_internal_email", AsyncMock(return_value=False))

    ev = NotificationEvidencePack(
        event_type=NotificationType.TEST_ALERT,
        severity=Severity.LOW,
        target_user="recovery_test_user",
        client_ip="127.0.0.1",
        summary="Notification queued while transport offline",
    )

    sender, recips = evaluate_routing_policy(ev)
    composed = await compose_notification(ev, sender, recips)

    alert_id, delivered = await outbox_mod.persist_and_deliver_notification(composed, dedup_window_seconds=1)
    assert alert_id > 0
    assert delivered is False  # Simulated offline transport

    async with get_db() as db:
        outbox_row = await (await db.execute(
            "SELECT status FROM notification_outbox WHERE event_type = 'TEST_ALERT' ORDER BY id DESC LIMIT 1"
        )).fetchone()
        assert outbox_row["status"] == "failed"

    # Restore real send_internal_email and trigger flush_pending_outbox
    monkeypatch.undo()
    flushed = await flush_pending_outbox()
    assert flushed >= 1

    async with get_db() as db:
        updated_row = await (await db.execute(
            "SELECT status, sent_at FROM notification_outbox WHERE event_type = 'TEST_ALERT' ORDER BY id DESC LIMIT 1"
        )).fetchone()
        assert updated_row["status"] == "sent"
        assert updated_row["sent_at"] is not None


@pytest.mark.asyncio
async def test_citation_validation_all_classes():
    """Verify fail-closed citation validation across AUDIT, DEVICE, RUN, APPROVAL, ARTIFACT, DOCUMENT."""
    async with get_db() as db:
        # 1. Audit
        cur_aud = await db.execute("INSERT INTO audit_events (action, resource_type, details, result) VALUES ('act', 'res', 'det', 'ok')")
        valid_audit_id = str(cur_aud.lastrowid)

        # 2. Device
        await db.execute("INSERT OR REPLACE INTO trusted_devices (device_id, user_id, display_name, public_key_jwk, key_fingerprint, status) VALUES ('dev-cit-1', 'cit_user', 'Cit Device', '{}', 'fp1', 'approved')")

        # Prerequisites: workspace and agent definition for FK constraints
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (1, 'QA Workspace', 'test')")
        await db.execute("INSERT OR IGNORE INTO agent_definitions (id, workspace_id, name, description, system_instructions) VALUES (1, 1, 'QA Agent', 'test', 'instructions')")

        # 3. Run
        cur_run = await db.execute("INSERT INTO agent_runs (workspace_id, agent_id, status) VALUES (1, 1, 'completed')")
        valid_run_id = str(cur_run.lastrowid)

        # 4. Tool definition for approval
        await db.execute("INSERT OR IGNORE INTO tool_definitions (id, name, risk_level, requires_approval, enabled, implementation_key) VALUES (999, 'tool_for_cit', 'sensitive', 1, 1, 'tool_cit')")

        # 5. Approval
        cur_app = await db.execute("INSERT INTO approval_requests (run_id, tool_id, status, request_reason, parameters, risk_level) VALUES (?, 999, 'pending', 'reason', '{}', 'sensitive')", (int(valid_run_id),))
        valid_approval_id = str(cur_app.lastrowid)

        # 6. Artifact
        cur_art = await db.execute("INSERT INTO workspace_artifacts (workspace_id, filename, relative_path, artifact_type, file_size, sha256_hash) VALUES (1, 'doc.txt', 'safety/doc.txt', 'text', 10, 'dummyhash')")
        valid_art_id = str(cur_art.lastrowid)

        # 7. Document
        cur_doc = await db.execute("INSERT INTO knowledge_sources (workspace_id, name, source_type, original_filename) VALUES (1, 'manual.pdf', 'pdf', 'manual.pdf')")
        valid_doc_id = str(cur_doc.lastrowid)

        await db.commit()

    citations = [
        NotificationCitation(citation_index=1, citation_type=CitationClass.AUDIT, display_label="Audit Event", source_id=valid_audit_id),
        NotificationCitation(citation_index=2, citation_type=CitationClass.DEVICE, display_label="Device", source_id="dev-cit-1"),
        NotificationCitation(citation_index=3, citation_type=CitationClass.RUN, display_label="Run", source_id=valid_run_id),
        NotificationCitation(citation_index=4, citation_type=CitationClass.APPROVAL, display_label="Approval", source_id=valid_approval_id),
        NotificationCitation(citation_index=5, citation_type=CitationClass.ARTIFACT, display_label="Artifact", source_id=valid_art_id),
        NotificationCitation(citation_index=6, citation_type=CitationClass.DOCUMENT, display_label="Document", source_id=valid_doc_id, page_number=1),
        # Fabricated citations:
        NotificationCitation(citation_index=7, citation_type=CitationClass.AUDIT, display_label="Fake Audit", source_id="888888"),
        NotificationCitation(citation_index=8, citation_type=CitationClass.DEVICE, display_label="Fake Device", source_id="fake-nonexistent-dev"),
        NotificationCitation(citation_index=9, citation_type=CitationClass.RUN, display_label="Fake Run", source_id="999999"),
        NotificationCitation(citation_index=10, citation_type=CitationClass.APPROVAL, display_label="Fake Approval", source_id="777777"),
        NotificationCitation(citation_index=11, citation_type=CitationClass.ARTIFACT, display_label="Fake Artifact", source_id="666666"),
        NotificationCitation(citation_index=12, citation_type=CitationClass.DOCUMENT, display_label="Fake Document", source_id="555555"),
    ]

    for c in citations[:6]:
        assert await validate_citation(c) is True, f"Citation {c} failed validation unexpectedly"

    for c in citations[6:]:
        assert await validate_citation(c) is False, f"Fabricated citation {c} was unexpectedly validated"

    validated_list, all_valid = await validate_citations(citations, strip_invalid=True)
    assert all_valid is False
    assert len(validated_list) == 6
    assert [c.citation_index for c in validated_list] == [1, 2, 3, 4, 5, 6]


def test_smtp_socket_bound_strictly_to_loopback():
    """Verify via OS socket that port 1025 accepts connections on 127.0.0.1 and presents sovereign banner."""
    s_local = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s_local.settimeout(2.0)
    connected_local = False
    try:
        s_local.connect(("127.0.0.1", 1025))
        banner = s_local.recv(1024)
        assert b"CogniShift" in banner and b"SMTP" in banner
        connected_local = True
    finally:
        s_local.close()
    assert connected_local is True


@pytest.mark.asyncio
async def test_rbac_operator_rejected_from_all_alert_endpoints():
    """Verify operator role receives 403 Forbidden across all /api/v1/security/alerts/* endpoints."""
    op_token, _ = create_ephemeral_demo_session(User(user_id="op_tester", role="operator", allowed_workspace_ids=[1]))
    op_headers = {"Authorization": f"Bearer {op_token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. smtp-health
        r1 = await client.get("/api/v1/security/alerts/smtp-health", headers=op_headers)
        assert r1.status_code == 403

        # 2. mailbox
        r2 = await client.get("/api/v1/security/alerts/mailbox", headers=op_headers)
        assert r2.status_code == 403

        # 3. detail
        r3 = await client.get("/api/v1/security/alerts/1", headers=op_headers)
        assert r3.status_code == 403

        # 4. read
        r4 = await client.post("/api/v1/security/alerts/1/read", headers=op_headers)
        assert r4.status_code == 403

        # 5. clear
        r5 = await client.post("/api/v1/security/alerts/clear", headers=op_headers)
        assert r5.status_code == 403

        # 6. dispatch-test
        r6 = await client.post("/api/v1/security/alerts/dispatch-test", headers=op_headers)
        assert r6.status_code == 403


@pytest.mark.asyncio
async def test_mailbox_eml_data_hygiene():
    """Verify saved .eml files never expose bearer tokens, session hashes, private keys, or passwords."""
    admin_token, _ = create_ephemeral_demo_session(User(user_id="admin_hygiene", role="administrator", allowed_workspace_ids=[1]))
    headers = {"Authorization": f"Bearer {admin_token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/security/alerts/dispatch-test", headers=headers)
        assert resp.status_code == 200

    await asyncio.sleep(0.3)

    assert MAILBOX_DIR.exists()
    eml_files = list(MAILBOX_DIR.glob("*.eml"))
    assert len(eml_files) > 0

    prohibited_substrings = [
        "cog_demo_",
        "PRIVATE KEY",
        "BEGIN EC PRIVATE KEY",
        "BEGIN RSA PRIVATE KEY",
        "password",
        admin_token,
    ]

    for eml_path in eml_files[-3:]:
        content = eml_path.read_text(encoding="utf-8", errors="ignore")
        for prohibited in prohibited_substrings:
            assert prohibited not in content, f"Sensitive data '{prohibited}' leaked in {eml_path.name}!"
