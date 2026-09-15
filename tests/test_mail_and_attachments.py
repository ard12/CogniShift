"""Comprehensive test suite for Internal User-to-User Mail, Attachments, SSE Streaming, and Security Hardening."""
import asyncio
import io
import json
import pytest
from httpx import ASGITransport, AsyncClient

from cognishift.app.core.auth import User, create_ephemeral_demo_session
from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from cognishift.app.main import app
from cognishift.core.authorizations import (
    request_temporary_authorization,
    approve_authorization_stage,
    process_pending_post_approval_jobs,
)
from cognishift.app.api.mail import _MAIL_EVENT_QUEUES, _EVENT_QUEUES_LOCK


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
    vicky = User(user_id="vicky", role="operator", allowed_workspace_ids=[1])
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
async def test_mail_recipients_directory(auth_personas):
    """Verify GET /api/v1/mail/recipients returns internal personas without credentials."""
    _, aryan_h = auth_personas["aryan"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/mail/recipients", headers=aryan_h)
        assert res.status_code == 200, res.text
        recipients = res.json()
        assert len(recipients) >= 4

        roles = {r["role"] for r in recipients}
        assert "administrator" in roles
        assert "operator" in roles

        for r in recipients:
            assert "user_id" in r
            assert "display_name" in r
            assert "role" in r
            assert "internal_email" in r
            # Security: credential store secrets must not leak
            for secret_key in ("password", "salt", "password_hash", "private_key", "jwk"):
                assert secret_key not in r


@pytest.mark.asyncio
async def test_send_user_mail_validation(auth_personas):
    """Verify input validation rules for sending internal mail."""
    _, aryan_h = auth_personas["aryan"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Empty subject
        r1 = await client.post(
            "/api/v1/mail/send",
            json={"recipients": ["zara"], "subject": "   ", "body_text": "Test body"},
            headers=aryan_h,
        )
        assert r1.status_code == 400
        assert "Subject cannot be empty" in r1.json()["detail"]

        # 2. Empty body
        r2 = await client.post(
            "/api/v1/mail/send",
            json={"recipients": ["zara"], "subject": "Valid Subject", "body_text": "  "},
            headers=aryan_h,
        )
        assert r2.status_code == 400
        assert "Message body cannot be empty" in r2.json()["detail"]

        # 3. No recipients
        r3 = await client.post(
            "/api/v1/mail/send",
            json={"recipients": [], "subject": "Valid Subject", "body_text": "Valid Body"},
            headers=aryan_h,
        )
        assert r3.status_code == 400
        assert "At least one recipient is required" in r3.json()["detail"]


@pytest.mark.asyncio
async def test_send_user_mail_delivery_and_folder_isolation(auth_personas):
    """Verify genuine user-to-user send, non-spoofed sender, per-recipient delivery, and folder isolation."""
    _, aryan_h = auth_personas["aryan"]
    _, zara_h = auth_personas["zara"]
    _, rohit_h = auth_personas["rohit"]
    _, vicky_h = auth_personas["vicky"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Aryan sends message to Zara and Rohit
        send_payload = {
            "recipients": ["zara@secure.internal", "rohit"],
            "subject": "Scheduled Inspection for Pump P-101A",
            "body_text": "Please confirm readiness for vibration diagnostics on pump P-101A at 14:00.",
        }
        send_res = await client.post("/api/v1/mail/send", json=send_payload, headers=aryan_h)
        assert send_res.status_code == 200, send_res.text
        data = send_res.json()
        assert data["status"] == "sent"
        alert_id = data["alert_id"]
        assert "zara" in data["recipients"]
        assert "rohit" in data["recipients"]

        # 1. Sender (Aryan) sees message in folder=sent
        sent_res = await client.get("/api/v1/mail?folder=sent", headers=aryan_h)
        assert sent_res.status_code == 200
        sent_ids = [m["id"] for m in sent_res.json()["messages"]]
        assert alert_id in sent_ids

        # 2. Recipient 1 (Zara) sees message in folder=inbox
        zara_inbox = await client.get("/api/v1/mail?folder=inbox", headers=zara_h)
        assert zara_inbox.status_code == 200
        zara_ids = [m["id"] for m in zara_inbox.json()["messages"]]
        assert alert_id in zara_ids

        # 3. Recipient 2 (Rohit) sees message in folder=inbox
        rohit_inbox = await client.get("/api/v1/mail?folder=inbox", headers=rohit_h)
        assert rohit_inbox.status_code == 200
        rohit_ids = [m["id"] for m in rohit_inbox.json()["messages"]]
        assert alert_id in rohit_ids

        # 4. Third-party Operator (Vicky) must NOT see the message in inbox
        vicky_inbox = await client.get("/api/v1/mail?folder=inbox", headers=vicky_h)
        assert vicky_inbox.status_code == 200
        vicky_ids = [m["id"] for m in vicky_inbox.json()["messages"]]
        assert alert_id not in vicky_ids

        # 5. Third-party Operator (Vicky) gets 403 trying to read the alert directly
        vicky_detail = await client.get(f"/api/v1/mail/{alert_id}", headers=vicky_h)
        assert vicky_detail.status_code == 403


@pytest.mark.asyncio
async def test_independent_per_recipient_read_tracking(auth_personas):
    """Verify that marking a mail as read by one recipient does not alter the read status for other recipients."""
    _, aryan_h = auth_personas["aryan"]
    _, zara_h = auth_personas["zara"]
    _, rohit_h = auth_personas["rohit"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        send_res = await client.post(
            "/api/v1/mail/send",
            json={
                "recipients": ["zara", "rohit"],
                "subject": "Independent Read State Test",
                "body_text": "Verifying multi-recipient read tracking.",
            },
            headers=aryan_h,
        )
        assert send_res.status_code == 200
        alert_id = send_res.json()["alert_id"]

        # Initial state: Zara sees unread
        zara_pre = await client.get(f"/api/v1/mail/{alert_id}", headers=zara_h)
        assert zara_pre.status_code == 200
        assert zara_pre.json()["is_read"] == 0

        # Zara marks message read
        read_res = await client.post(f"/api/v1/mail/{alert_id}/read", headers=zara_h)
        assert read_res.status_code == 200
        assert read_res.json()["is_read"] == 1

        # Zara detail now shows read
        zara_post = await client.get(f"/api/v1/mail/{alert_id}", headers=zara_h)
        assert zara_post.status_code == 200
        assert zara_post.json()["is_read"] == 1

        # Rohit detail must STILL show unread
        rohit_check = await client.get(f"/api/v1/mail/{alert_id}", headers=rohit_h)
        assert rohit_check.status_code == 200
        assert rohit_check.json()["is_read"] == 0


@pytest.mark.asyncio
async def test_attachment_upload_extension_and_size_enforcement(auth_personas):
    """Verify attachment extension whitelist, blacklist rejection, and 10MB file size cap."""
    _, aryan_h = auth_personas["aryan"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Allowed text file upload
        txt_content = b"Sensor Reading: 101.4 kPa normal operating condition."
        res_txt = await client.post(
            "/api/v1/mail/attachments/upload",
            files={"file": ("pressure_log.txt", txt_content, "text/plain")},
            headers=aryan_h,
        )
        assert res_txt.status_code == 200, res_txt.text
        data_txt = res_txt.json()
        assert data_txt["id"] > 0
        assert data_txt["filename"] == "pressure_log.txt"
        assert data_txt["file_size"] == len(txt_content)
        assert "sha256" in data_txt

        # 2. Blocked executable extension (.exe)
        res_exe = await client.post(
            "/api/v1/mail/attachments/upload",
            files={"file": ("malicious_payload.exe", b"MZ\x90\x00", "application/x-msdownload")},
            headers=aryan_h,
        )
        assert res_exe.status_code == 400
        assert "not permitted" in res_exe.json()["detail"]

        # 3. Blocked script extension (.py)
        res_py = await client.post(
            "/api/v1/mail/attachments/upload",
            files={"file": ("exploit.py", b"import subprocess", "text/x-python")},
            headers=aryan_h,
        )
        assert res_py.status_code == 400
        assert "not permitted" in res_py.json()["detail"]

        # 4. Oversized upload (> 10 MiB)
        # Create an in-memory stream of 10.5 MiB
        oversized_data = b"0" * (10 * 1024 * 1024 + 1024)
        res_large = await client.post(
            "/api/v1/mail/attachments/upload",
            files={"file": ("huge_dump.csv", oversized_data, "text/csv")},
            headers=aryan_h,
        )
        assert res_large.status_code == 413
        assert "maximum permitted size" in res_large.json()["detail"]


@pytest.mark.asyncio
async def test_attachment_link_to_mail_and_authorized_download(auth_personas):
    """Verify staging an attachment, associating it with sent mail, and role-based download authorization."""
    _, aryan_h = auth_personas["aryan"]
    _, zara_h = auth_personas["zara"]
    _, rohit_h = auth_personas["rohit"]
    _, vicky_h = auth_personas["vicky"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Aryan uploads attachment
        pdf_bytes = b"%PDF-1.4 sample plant schematic diagram content"
        up_res = await client.post(
            "/api/v1/mail/attachments/upload",
            files={"file": ("schematic_p101a.pdf", pdf_bytes, "application/pdf")},
            headers=aryan_h,
        )
        assert up_res.status_code == 200
        att_id = up_res.json()["id"]

        # Step 2: Aryan sends mail linking the attachment to Zara
        send_res = await client.post(
            "/api/v1/mail/send",
            json={
                "recipients": ["zara"],
                "subject": "Attached P-101A Schematic",
                "body_text": "Please review the attached schematic before maintenance.",
                "attachment_ids": [att_id],
            },
            headers=aryan_h,
        )
        assert send_res.status_code == 200
        alert_id = send_res.json()["alert_id"]
        assert send_res.json()["attachments_count"] == 1

        # Step 3: Zara inspects mail detail and sees attachment
        zara_detail = await client.get(f"/api/v1/mail/{alert_id}", headers=zara_h)
        assert zara_detail.status_code == 200
        atts = zara_detail.json()["attachments"]
        assert len(atts) == 1
        assert atts[0]["id"] == att_id
        assert atts[0]["filename"] == "schematic_p101a.pdf"

        # Step 4: Recipient (Zara) downloads attachment
        dl_zara = await client.get(f"/api/v1/mail/{alert_id}/attachments/{att_id}", headers=zara_h)
        assert dl_zara.status_code == 200
        assert dl_zara.content == pdf_bytes

        # Step 5: Sender (Aryan) downloads attachment
        dl_aryan = await client.get(f"/api/v1/mail/{alert_id}/attachments/{att_id}", headers=aryan_h)
        assert dl_aryan.status_code == 200
        assert dl_aryan.content == pdf_bytes

        # Step 6: Administrator (Rohit) downloads attachment
        dl_rohit = await client.get(f"/api/v1/mail/{alert_id}/attachments/{att_id}", headers=rohit_h)
        assert dl_rohit.status_code == 200
        assert dl_rohit.content == pdf_bytes

        # Step 7: Unauthorized Operator (Vicky) gets 403 Forbidden
        dl_vicky = await client.get(f"/api/v1/mail/{alert_id}/attachments/{att_id}", headers=vicky_h)
        assert dl_vicky.status_code == 403

        # Step 8: Verify audit trail
        async with get_db() as db:
            audit = await (await db.execute(
                "SELECT * FROM audit_events WHERE action = 'MAIL_ATTACHMENT_DOWNLOADED' AND resource_id = ? ORDER BY id DESC LIMIT 1",
                (att_id,),
            )).fetchone()
        assert audit is not None
        assert audit["result"] == "success"

        # Step 9: A tampered DB path inside data/, but outside mail/attachments/, is rejected.
        async with get_db() as db:
            await db.execute(
                "UPDATE mail_attachments SET storage_path = ? WHERE id = ?",
                (str(settings.data_dir / "cognishift.db"), att_id),
            )
            await db.commit()
        dl_tampered = await client.get(
            f"/api/v1/mail/{alert_id}/attachments/{att_id}", headers=aryan_h
        )
        assert dl_tampered.status_code == 400
        assert "Invalid attachment storage path" in dl_tampered.json()["detail"]


@pytest.mark.asyncio
async def test_permit_docx_attachment_linkage(auth_personas):
    """Verify that when a Four-Eyes permit is activated, the generated permit DOCX artifact
    is automatically linked to the notification in mail_attachments.
    """
    _, aryan_h = auth_personas["aryan"]
    _, zara_h = auth_personas["zara"]
    _, rakshita_h = auth_personas["rakshita"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Request permit
        p_res = await client.post(
            "/api/v1/authorizations",
            json={
                "workspace_id": 1,
                "user_id": "aryan",
                "action": "operate_pump",
                "resource": "P-101A",
                "reason": "Routine transfer per standard operating procedure",
                "max_uses": 1,
                "valid_minutes": 60,
            },
            headers=aryan_h,
        )
        assert p_res.status_code == 201
        permit_id = p_res.json()["id"]

        # Dual supervisor approval
        await client.post(f"/api/v1/authorizations/{permit_id}/approve", json={"comments": "S1 OK"}, headers=zara_h)
        act_res = await client.post(f"/api/v1/authorizations/{permit_id}/approve", json={"comments": "S2 OK"}, headers=rakshita_h)
        assert act_res.status_code == 200
        assert act_res.json()["status"] == "ACTIVE"

        # Durable worker processes post-approval jobs
        await asyncio.sleep(0.1)
        await process_pending_post_approval_jobs()

        # Retrieve job details
        async with get_db() as db:
            job = await (await db.execute(
                "SELECT alert_id, artifact_id FROM post_approval_jobs WHERE permit_id = ?",
                (permit_id,),
            )).fetchone()
            assert job is not None
            assert job["alert_id"] is not None
            alert_id = job["alert_id"]

            # Verify attachment registered in mail_attachments
            att = await (await db.execute(
                "SELECT * FROM mail_attachments WHERE alert_id = ?",
                (alert_id,),
            )).fetchone()
            assert att is not None
            assert att["filename"].endswith(".docx")
            assert "application/vnd.openxmlformats" in att["content_type"]

        # Operator (Aryan) views permit notification and sees the DOCX attachment
        mail_res = await client.get(f"/api/v1/mail/{alert_id}", headers=aryan_h)
        assert mail_res.status_code == 200
        mail_data = mail_res.json()
        assert len(mail_data["attachments"]) >= 1
        assert mail_data["attachments"][0]["filename"].endswith(".docx")

        # Operator can download the permit DOCX attachment
        att_id = mail_data["attachments"][0]["id"]
        dl = await client.get(f"/api/v1/mail/{alert_id}/attachments/{att_id}", headers=aryan_h)
        assert dl.status_code == 200
        assert len(dl.content) > 0


@pytest.mark.asyncio
async def test_mail_draft_assist_with_fallback(auth_personas):
    """Verify POST /api/v1/mail/draft/assist generates structured subject and body with deterministic fallback."""
    _, aryan_h = auth_personas["aryan"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Successful draft assist call
        res = await client.post(
            "/api/v1/mail/draft/assist",
            json={
                "intent": "Notify instrumentation crew to calibrate thermocouple TE-204 prior to unit restart",
                "context": "Shutdown completed at 06:00, maintenance window closes at 16:00",
                "tone": "urgent",
            },
            headers=aryan_h,
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "subject" in data and len(data["subject"]) > 0
        assert "body" in data and len(data["body"]) > 0
        assert "model" in data
        assert "latency_ms" in data
        assert data["latency_ms"] >= 0

        # 2. Empty intent validation
        res_empty = await client.post(
            "/api/v1/mail/draft/assist",
            json={"intent": "   "},
            headers=aryan_h,
        )
        assert res_empty.status_code == 400


@pytest.mark.asyncio
async def test_sse_events_stream_and_disconnect(auth_personas):
    """Verify GET /api/v1/mail/events establishes SSE connection, yields connected event, and cleans up queue."""
    _, aryan_h = auth_personas["aryan"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Connect to SSE stream with limit=1 (emits initial connected event and completes)
        async with client.stream("GET", "/api/v1/mail/events?limit=1", headers=aryan_h) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            # Consume streamed lines
            received_lines = []
            async for line in response.aiter_lines():
                received_lines.append(line)

            stream_content = "\n".join(received_lines)
            assert "event: connected" in stream_content
            assert "aryan" in stream_content

        # Disconnect occurred: verify generator cleanup discarded queue from global dict
        with _EVENT_QUEUES_LOCK:
            aryan_queues = _MAIL_EVENT_QUEUES.get("aryan", set())
            assert len(aryan_queues) == 0

        # Test broadcast_mail_event delivery to an active subscriber queue
        test_q = asyncio.Queue()
        with _EVENT_QUEUES_LOCK:
            _MAIL_EVENT_QUEUES["aryan"].add(test_q)
        try:
            from cognishift.app.api.mail import broadcast_mail_event
            await broadcast_mail_event(["aryan"], "test_push", {"msg": "live_delivery"})
            assert not test_q.empty()
            item = test_q.get_nowait()
            assert item["event"] == "test_push"
            assert item["data"]["msg"] == "live_delivery"
        finally:
            with _EVENT_QUEUES_LOCK:
                _MAIL_EVENT_QUEUES.get("aryan", set()).discard(test_q)
