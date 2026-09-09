"""REST APIs for Role-Scoped Sovereign Internal Mailbox & Communication.

Domain prefix: /api/v1/mail
Provides role-scoped email client endpoints:
- Operators: view only emails addressed to their own user identity + sent messages
- Supervisors: view own emails + governance / approval notifications + sent messages
- Administrators: view full SOC security, system, and governance feeds
- Genuine user-to-user messaging (POST /send) with independent per-recipient read tracking
- First-class attachment upload & safe download with extension whitelist and size caps
- Real-time Server-Sent Events (GET /events) with graceful disconnect & cancellation handling
- Local LLM mail assist (POST /draft/assist) with audited latency and deterministic fallback
- Lightweight metadata listing to prevent memory/payload bloat
"""
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
import logging
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, List, Optional, Set
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from cognishift.app.config import settings
from cognishift.app.core.auth import (
    LOCAL_CREDENTIAL_STORE,
    User,
    get_current_user,
    load_credential_store,
    refresh_credential_store_if_changed,
)
from cognishift.app.db.database import get_db
from cognishift.core.time_utils import now_iso_utc, normalize_iso_utc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mail", tags=["Mailbox"])

# Attachment Security Constraints
ALLOWED_ATTACHMENT_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".csv", ".txt", ".png", ".jpg", ".jpeg"}
BLOCKED_ATTACHMENT_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".sh", ".dll", ".vbs", ".msi", ".jar", ".py", ".bin"}
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MiB

# Real-Time SSE Event Queues
_MAIL_EVENT_QUEUES: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
_EVENT_QUEUES_LOCK = threading.Lock()


async def broadcast_mail_event(target_users: List[str], event_type: str, data: Dict[str, Any]) -> None:
    """Broadcast event payload to active SSE queues for specified user IDs."""
    payload = {"event": event_type, "data": data}
    with _EVENT_QUEUES_LOCK:
        for uid in target_users:
            queues = _MAIL_EVENT_QUEUES.get(uid, set())
            for q in list(queues):
                try:
                    q.put_nowait(payload)
                except Exception:
                    pass


# -----------------------------------------------------------------------------
# PYDANTIC SCHEMAS
# -----------------------------------------------------------------------------
class SendMailRequest(BaseModel):
    recipients: List[str]
    subject: str
    body_text: str
    body_html: Optional[str] = None
    attachment_ids: Optional[List[int]] = None


class DraftAssistRequest(BaseModel):
    intent: str
    context: Optional[str] = None
    tone: Optional[str] = "professional"


# -----------------------------------------------------------------------------
# STATIC ROUTES (MUST BE DEFINED BEFORE PARAMETERIZED ROUTES)
# -----------------------------------------------------------------------------
@router.get("")
async def list_mailbox_messages(
    limit: int = 50,
    offset: int = 0,
    folder: Optional[str] = None,  # "all", "inbox", "sent", "permits", "security", "governance"
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve role-scoped message list metadata. Full body/citations excluded for performance."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    async with get_db() as db:
        query_parts: List[str] = []
        params: List[Any] = []

        if folder == "sent":
            base_sql = "FROM offline_security_alerts a WHERE (a.sender_user_id = ? OR a.sender LIKE ?)"
            params.append(user.user_id)
            params.append(f"{user.user_id}@%")
        elif user.role == "administrator":
            # Administrator SOC view: sees all alerts with admin-specific delivery state
            base_sql = """
                FROM offline_security_alerts a
                LEFT JOIN (
                    SELECT alert_id, MAX(is_read) as is_read, MAX(read_at) as read_at
                    FROM notification_recipient_deliveries
                    WHERE recipient_user_id IN (?, 'admin', 'sitanshu')
                    GROUP BY alert_id
                ) d ON a.id = d.alert_id
                WHERE 1=1
            """
            params.append(user.user_id)
        elif user.role == "supervisor":
            # Supervisor sees messages addressed to them or governance events
            base_sql = """
                FROM offline_security_alerts a
                JOIN (
                    SELECT alert_id, MAX(is_read) as is_read, MAX(read_at) as read_at
                    FROM notification_recipient_deliveries
                    WHERE recipient_user_id = ?
                    GROUP BY alert_id
                ) d ON a.id = d.alert_id
                WHERE 1=1
            """
            params.append(user.user_id)
        else:
            # Operator sees only messages delivered to them
            base_sql = """
                FROM offline_security_alerts a
                JOIN (
                    SELECT alert_id, MAX(is_read) as is_read, MAX(read_at) as read_at
                    FROM notification_recipient_deliveries
                    WHERE recipient_user_id = ?
                    GROUP BY alert_id
                ) d ON a.id = d.alert_id
                WHERE 1=1
            """
            params.append(user.user_id)

        # Folder filtering
        if folder == "permits":
            query_parts.append("AND a.alert_type IN ('ACCESS_AUTHORIZATION', 'AUTHORIZATION_CONSUMED')")
        elif folder == "security":
            query_parts.append(
                "AND a.alert_type IN ('UNTRUSTED_DEVICE', 'NETWORK_DRIFT', 'FOREIGN_NETWORK_OBSERVED', 'DEVICE_BLOCKED', 'DEVICE_REVOKED')"
            )
        elif folder == "governance":
            query_parts.append(
                "AND a.alert_type IN ('SENSITIVE_ACTION_REQUESTED', 'FIRST_SUPERVISOR_APPROVAL', 'FOUR_EYES_COMPLETED', 'ACCESS_AUTHORIZATION')"
            )

        filter_sql = " ".join(query_parts)

        # Unread count
        if folder == "sent":
            unread_count = 0
        elif user.role == "administrator":
            unread_sql = f"SELECT count(*) as unread {base_sql} {filter_sql} AND (COALESCE(d.is_read, a.is_read, 0) = 0)"
            unread_row = await (await db.execute(unread_sql, tuple(params))).fetchone()
            unread_count = unread_row["unread"] if unread_row else 0
        else:
            unread_sql = f"SELECT count(*) as unread {base_sql} {filter_sql} AND (COALESCE(d.is_read, 0) = 0)"
            unread_row = await (await db.execute(unread_sql, tuple(params))).fetchone()
            unread_count = unread_row["unread"] if unread_row else 0

        # Total count
        total_sql = f"SELECT count(*) as total {base_sql} {filter_sql}"
        total_row = await (await db.execute(total_sql, tuple(params))).fetchone()
        total_count = total_row["total"] if total_row else 0

        # Select lightweight metadata
        if folder == "sent":
            select_sql = f"""
                SELECT
                    a.id,
                    a.alert_type,
                    a.severity,
                    a.subject,
                    a.sender,
                    a.recipients,
                    a.composition_mode,
                    a.related_user,
                    a.related_ip,
                    a.related_run_id,
                    a.created_at,
                    1 as is_read,
                    NULL as read_at
                {base_sql}
                {filter_sql}
                ORDER BY a.created_at DESC
                LIMIT ? OFFSET ?
            """
        else:
            select_sql = f"""
                SELECT
                    a.id,
                    a.alert_type,
                    a.severity,
                    a.subject,
                    a.sender,
                    a.recipients,
                    a.composition_mode,
                    a.related_user,
                    a.related_ip,
                    a.related_run_id,
                    a.created_at,
                    COALESCE(d.is_read, a.is_read, 0) as is_read,
                    d.read_at
                {base_sql}
                {filter_sql}
                ORDER BY a.created_at DESC
                LIMIT ? OFFSET ?
            """

        fetch_params = list(params) + [limit, offset]
        rows = await (await db.execute(select_sql, tuple(fetch_params))).fetchall()

        messages = []
        for r in rows:
            d = dict(r)
            try:
                d["recipients"] = json.loads(d["recipients"])
            except Exception:
                d["recipients"] = [str(d.get("recipients", ""))]
            d["created_at"] = normalize_iso_utc(d.get("created_at"))
            d["read_at"] = normalize_iso_utc(d.get("read_at"))
            messages.append(d)

        return {
            "messages": messages,
            "unread_count": unread_count,
            "total_count": total_count,
            "role": user.role,
            "user_id": user.user_id,
        }


@router.get("/recipients")
async def list_recipients(
    user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Directory of internal team members/personas for recipient autocomplete without credentials."""
    refresh_credential_store_if_changed()
    if not LOCAL_CREDENTIAL_STORE:
        load_credential_store()

    recipients = []
    seen = set()
    for rec in LOCAL_CREDENTIAL_STORE.values():
        if not rec.enabled or rec.user_id in seen:
            continue
        seen.add(rec.user_id)
        display = rec.user_id.replace("_", " ").title()
        recipients.append({
            "user_id": rec.user_id,
            "display_name": display,
            "role": rec.role,
            "internal_email": f"{rec.user_id}@secure.internal",
        })

    role_priority = {"administrator": 0, "supervisor": 1, "operator": 2}
    recipients.sort(key=lambda x: (role_priority.get(x["role"], 99), x["display_name"]))
    return recipients


@router.post("/send")
async def send_user_mail(
    req: SendMailRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Send genuine internal user-to-user mail with optional attachments and SSE broadcast."""
    subject = req.subject.strip()
    if not subject:
        raise HTTPException(status_code=400, detail="Subject cannot be empty.")
    if len(subject) > 250:
        raise HTTPException(status_code=400, detail="Subject cannot exceed 250 characters.")

    body_text = req.body_text.strip()
    if not body_text:
        raise HTTPException(status_code=400, detail="Message body cannot be empty.")
    if len(body_text) > 50000:
        raise HTTPException(status_code=400, detail="Message body cannot exceed 50,000 characters.")

    if not req.recipients:
        raise HTTPException(status_code=400, detail="At least one recipient is required.")

    # Normalize recipient identifiers
    resolved_recipients = []
    for r in req.recipients:
        cleaned = r.strip().lower()
        if "@" in cleaned:
            cleaned = cleaned.split("@")[0]
        if cleaned and cleaned not in resolved_recipients:
            resolved_recipients.append(cleaned)

    if not resolved_recipients:
        raise HTTPException(status_code=400, detail="No valid recipients specified.")

    now_str = now_iso_utc()
    sender_email = f"{user.user_id}@secure.internal"
    recipient_emails = [f"{r}@secure.internal" for r in resolved_recipients]

    escaped_body = html.escape(body_text).replace("\n", "<br/>")
    body_html = req.body_html or (
        f"<div style='font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; "
        f"line-height: 1.6; color: #1e293b; padding: 12px; background: #ffffff; border-radius: 8px;'>"
        f"{escaped_body}"
        f"</div>"
    )

    async with get_db() as db:
        cur = await db.execute(
            """
            INSERT INTO offline_security_alerts (
                alert_type, severity, subject, sender, sender_user_id, is_user_mail, delivery_status,
                recipients, body_text, body_html, composition_mode, evidence_pack_json, related_user, is_read, created_at
            ) VALUES ('USER_MESSAGE', 'LOW', ?, ?, ?, 1, 'DELIVERED', ?, ?, ?, 'USER_COMPOSED', ?, ?, 0, ?)
            RETURNING id
            """,
            (
                subject,
                sender_email,
                user.user_id,
                json.dumps(recipient_emails),
                body_text,
                body_html,
                json.dumps({"sender": user.user_id, "recipients": resolved_recipients}),
                user.user_id,
                now_str,
            ),
        )
        row = await cur.fetchone()
        alert_id = row["id"]

        # Insert per-recipient delivery records
        for recip in resolved_recipients:
            await db.execute(
                """
                INSERT INTO notification_recipient_deliveries (
                    alert_id, recipient_email, recipient_user_id, is_read, created_at
                ) VALUES (?, ?, ?, 0, ?)
                """,
                (alert_id, f"{recip}@secure.internal", recip, now_str),
            )

        # Associate any staged attachments uploaded by this user
        linked_attachment_count = 0
        if req.attachment_ids:
            placeholders = ",".join("?" for _ in req.attachment_ids)
            att_cur = await db.execute(
                f"""
                UPDATE mail_attachments
                SET alert_id = ?
                WHERE id IN ({placeholders}) AND (uploader_user_id = ? OR uploader_user_id IS NULL)
                """,
                [alert_id] + req.attachment_ids + [user.user_id],
            )
            linked_attachment_count = att_cur.rowcount

        # Insert audit log for sent message
        await db.execute(
            """
            INSERT INTO audit_events (
                actor_id, action, resource_type, resource_id, details, result, created_at
            ) VALUES (?, 'MAIL_SENT', 'offline_security_alert', ?, ?, 'success', ?)
            """,
            (
                user.user_id,
                alert_id,
                json.dumps({
                    "sender": user.user_id,
                    "recipients": resolved_recipients,
                    "subject": subject,
                    "attachments": linked_attachment_count,
                }),
                now_str,
            ),
        )
        await db.commit()

    # Real-time SSE broadcast to recipients
    await broadcast_mail_event(
        target_users=resolved_recipients,
        event_type="new_mail",
        data={
            "id": alert_id,
            "subject": subject,
            "sender": sender_email,
            "created_at": now_str,
            "is_user_mail": True,
        },
    )

    return {
        "status": "sent",
        "alert_id": alert_id,
        "recipients": resolved_recipients,
        "attachments_count": linked_attachment_count,
        "created_at": now_str,
    }


@router.post("/attachments/upload")
async def upload_attachment(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Upload a safe attachment prior to message dispatch with strict validation."""
    original_filename = file.filename or "attachment.bin"
    ext = Path(original_filename).suffix.lower()

    if ext in BLOCKED_ATTACHMENT_EXTENSIONS or ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File extension '{ext}' is not permitted. Allowed: {', '.join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS))}",
        )

    # Sanitize filename
    base = re.sub(r"[^a-zA-Z0-9_.-]", "_", Path(original_filename).stem)
    safe_name = f"{base}{ext}"
    attachment_uuid = uuid.uuid4().hex
    target_filename = f"{attachment_uuid}_{safe_name}"

    attach_dir = settings.data_dir / "mail" / "attachments"
    attach_dir.mkdir(parents=True, exist_ok=True)
    target_path = attach_dir / target_filename

    # Read and stream with size cap and SHA-256 hash calculation
    hasher = hashlib.sha256()
    total_bytes = 0
    oversized = False

    with open(target_path, "wb") as f_out:
        while chunk := await file.read(64 * 1024):
            total_bytes += len(chunk)
            if total_bytes > MAX_ATTACHMENT_BYTES:
                oversized = True
                break
            hasher.update(chunk)
            f_out.write(chunk)

    if oversized:
        target_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=413,
            detail=f"Attachment exceeds maximum permitted size of 10MB.",
        )

    sha256_hex = hasher.hexdigest()
    now_str = now_iso_utc()

    async with get_db() as db:
        cur = await db.execute(
            """
            INSERT INTO mail_attachments (
                alert_id, uploader_user_id, filename, content_type, file_size, storage_path,
                sha256_hash, created_at
            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                user.user_id,
                safe_name,
                file.content_type or "application/octet-stream",
                total_bytes,
                str(target_path),
                sha256_hex,
                now_str,
            ),
        )
        row = await cur.fetchone()
        att_id = row["id"]
        await db.commit()

    return {
        "id": att_id,
        "filename": safe_name,
        "file_size": total_bytes,
        "content_type": file.content_type or "application/octet-stream",
        "sha256": sha256_hex,
    }


@router.get("/events")
async def stream_mail_events(
    request: Request,
    user: User = Depends(get_current_user),
    limit: Optional[int] = None,
):
    """Server-Sent Events endpoint for real-time mailbox push notifications with disconnect safety."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    with _EVENT_QUEUES_LOCK:
        _MAIL_EVENT_QUEUES[user.user_id].add(queue)

    async def event_generator():
        emitted = 0
        try:
            yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'user_id': user.user_id})}\n\n"
            emitted += 1
            if limit is not None and emitted >= limit:
                return

            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
                    emitted += 1
                    if limit is not None and emitted >= limit:
                        break
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            with _EVENT_QUEUES_LOCK:
                user_set = _MAIL_EVENT_QUEUES.get(user.user_id)
                if user_set:
                    user_set.discard(queue)
                    if not user_set:
                        _MAIL_EVENT_QUEUES.pop(user.user_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/draft/assist")
async def draft_mail_assist(
    req: DraftAssistRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate professional operational mail draft using local Ollama model with deterministic fallback."""
    t0 = time.perf_counter()
    intent = req.intent.strip()
    if not intent:
        raise HTTPException(status_code=400, detail="Draft intent prompt cannot be empty.")

    system_prompt = (
        "You are an industrial operations communication assistant for an on-premise sovereign plant workbench. "
        "Draft a clear, concise operational email. "
        "Return ONLY a valid JSON object with exactly two keys: 'subject' (a clear concise subject line) and 'body' (the email text). "
        "Do not include any conversational filler, markdown codeblocks (no ```json), or extra text."
    )
    user_prompt = f"Intent: {intent}\nContext: {req.context or 'None'}\nTone: {req.tone or 'professional'}\nSender Role: {user.role}"

    subject_res = ""
    body_res = ""
    used_fallback = False
    model_name = settings.text_model

    try:
        from cognishift.core.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        resp = await asyncio.wait_for(
            provider.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model_name=model_name,
            ),
            timeout=6.0,
        )
        raw_text = resp.text.strip()
        if "{" in raw_text and "}" in raw_text:
            json_str = raw_text[raw_text.find("{") : raw_text.rfind("}") + 1]
            data = json.loads(json_str)
            subject_res = str(data.get("subject", "")).strip()
            body_res = str(data.get("body", "")).strip()
        if not subject_res or not body_res:
            used_fallback = True
    except Exception as err:
        logger.info(f"Ollama draft assist fallback triggered: {err}")
        used_fallback = True

    if used_fallback:
        subject_res = f"[Operational Request] {intent[:60]}"
        body_res = (
            f"Dear Team,\n\n"
            f"Regarding: {intent}\n\n"
            f"Please be advised of the operational status and requirements detailed above. "
            f"All actions must proceed in accordance with standard safety operating procedures.\n\n"
            f"Regards,\n{user.user_id.replace('_', ' ').title()}\nRole: {user.role.title()}"
        )

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "subject": subject_res,
        "body": body_res,
        "model": model_name if not used_fallback else "deterministic_fallback",
        "latency_ms": latency_ms,
        "fallback": used_fallback,
    }


@router.get("/smtp-health")
async def get_smtp_health() -> Dict[str, Any]:
    """Verify health and reachability of the local loopback SMTP listener."""
    from cognishift.core.notifications.smtp_transport import check_smtp_health

    return await check_smtp_health()


@router.post("/dispatch-test")
async def dispatch_test_email(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Dispatch a test alert through the local loopback notification pipeline."""
    if user.role not in ("supervisor", "administrator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisors and administrators only.",
        )
    from cognishift.core.notifications import (
        CitationClass,
        NotificationCitation,
        NotificationEvidencePack,
        NotificationType,
        Severity,
        dispatch_notification_for_event,
    )

    ev = NotificationEvidencePack(
        event_type=NotificationType.TEST_ALERT,
        severity=Severity.LOW,
        actor_id=user.user_id,
        target_user=user.user_id,
        client_ip="127.0.0.1",
        summary="Verified test dispatch to validate end-to-end local SMTP delivery on 127.0.0.1:1025.",
        citations=[
            NotificationCitation(
                citation_index=1,
                citation_type=CitationClass.AUDIT,
                display_label="Test Pipeline Verification",
                source_id="1",
                validated=True,
            )
        ],
    )
    alert_id, composed, delivered = await dispatch_notification_for_event(ev)
    return {
        "status": "dispatched",
        "alert_id": alert_id,
        "subject": composed.subject,
        "delivered": delivered,
        "composition_mode": composed.composition_mode,
    }


@router.post("/clear")
async def clear_mailbox(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Purge alerts, deliveries, and attachments (Administrator only)."""
    if user.role != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")

    async with get_db() as db:
        await db.execute("DELETE FROM notification_citations")
        await db.execute("DELETE FROM notification_recipient_deliveries")
        await db.execute("DELETE FROM mail_attachments")
        del_a = await db.execute("DELETE FROM offline_security_alerts")
        count = del_a.rowcount
        await db.commit()

    return {"status": "cleared", "deleted_count": count}


# -----------------------------------------------------------------------------
# PARAMETERIZED ROUTES
# -----------------------------------------------------------------------------
@router.get("/{alert_id}/attachments/{attachment_id}")
async def download_attachment(
    alert_id: int,
    attachment_id: int,
    user: User = Depends(get_current_user),
):
    """Download mail attachment with verified recipient/sender authorization and path traversal check."""
    async with get_db() as db:
        alert_row = await (await db.execute(
            "SELECT * FROM offline_security_alerts WHERE id = ?",
            (alert_id,),
        )).fetchone()
        if not alert_row:
            raise HTTPException(status_code=404, detail="Mail message not found.")

        is_sender = (alert_row["sender_user_id"] == user.user_id) or (
            alert_row["sender"] == f"{user.user_id}@secure.internal"
        )
        if user.role != "administrator" and not is_sender:
            has_access = await (await db.execute(
                """SELECT id FROM notification_recipient_deliveries
                   WHERE alert_id = ? AND (recipient_user_id = ? OR recipient_email = ?)""",
                (alert_id, user.user_id, f"{user.user_id}@secure.internal"),
            )).fetchone()
            if not has_access:
                raise HTTPException(status_code=403, detail="Access denied to this message attachment.")

        att_row = await (await db.execute(
            "SELECT * FROM mail_attachments WHERE id = ? AND alert_id = ?",
            (attachment_id, alert_id),
        )).fetchone()
        if not att_row:
            raise HTTPException(status_code=404, detail="Attachment not found.")

        # Path traversal guard
        file_path = Path(att_row["storage_path"]).resolve()
        if att_row["artifact_id"] is not None:
            artifact_row = await (await db.execute(
                "SELECT workspace_id, relative_path FROM workspace_artifacts WHERE id = ?",
                (att_row["artifact_id"],),
            )).fetchone()
            if not artifact_row:
                raise HTTPException(status_code=400, detail="Invalid attachment artifact link.")
            from cognishift.core.security import resolve_workspace_path

            expected_path = resolve_workspace_path(
                artifact_row["workspace_id"], artifact_row["relative_path"], purpose="read"
            ).resolve()
            if file_path != expected_path:
                raise HTTPException(status_code=400, detail="Invalid attachment storage path.")
        else:
            attachments_root = (settings.data_dir / "mail" / "attachments").resolve()
            try:
                file_path.relative_to(attachments_root)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid attachment storage path.")

        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="Attachment file not found on disk.")

        # Audit log
        await db.execute(
            """
            INSERT INTO audit_events (
                actor_id, action, resource_type, resource_id, details, result, created_at
            ) VALUES (?, 'MAIL_ATTACHMENT_DOWNLOADED', 'mail_attachment', ?, ?, 'success', ?)
            """,
            (
                user.user_id,
                attachment_id,
                json.dumps({"alert_id": alert_id, "filename": att_row["filename"]}),
                now_iso_utc(),
            ),
        )
        await db.commit()

    return FileResponse(
        path=file_path,
        filename=att_row["filename"],
        media_type=att_row["content_type"],
    )


@router.get("/{alert_id}")
async def get_mail_detail(
    alert_id: int,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve full email details including HTML body, text, attachments, and citations."""
    async with get_db() as db:
        row = await (await db.execute(
            "SELECT * FROM offline_security_alerts WHERE id = ?",
            (alert_id,),
        )).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Mail message not found.")

        # Access control: verify user has a delivery record, is sender, or is administrator
        is_sender = (row["sender_user_id"] == user.user_id) or (row["sender"] == f"{user.user_id}@secure.internal")
        if user.role != "administrator" and not is_sender:
            has_access = await (await db.execute(
                """SELECT id FROM notification_recipient_deliveries 
                   WHERE alert_id = ? AND (recipient_user_id = ? OR recipient_email = ?)""",
                (alert_id, user.user_id, f"{user.user_id}@secure.internal"),
            )).fetchone()
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: this notification is not addressed to your user account.",
                )

        deliv = await (await db.execute(
            "SELECT is_read, read_at FROM notification_recipient_deliveries WHERE alert_id = ? AND recipient_user_id = ?",
            (alert_id, user.user_id),
        )).fetchone()

        citations = await (await db.execute(
            "SELECT * FROM notification_citations WHERE alert_id = ? ORDER BY citation_index ASC",
            (alert_id,),
        )).fetchall()

        attachments = await (await db.execute(
            "SELECT id, filename, content_type, file_size, sha256_hash FROM mail_attachments WHERE alert_id = ?",
            (alert_id,),
        )).fetchall()

        d = dict(row)
        try:
            d["recipients"] = json.loads(d["recipients"])
        except Exception:
            pass
        try:
            d["evidence_pack"] = json.loads(d["evidence_pack_json"])
        except Exception:
            d["evidence_pack"] = {}

        d["citations"] = [dict(c) for c in citations]
        d["attachments"] = [dict(a) for a in attachments]
        d["created_at"] = normalize_iso_utc(d.get("created_at"))
        d["is_read"] = deliv["is_read"] if deliv else (1 if is_sender else d.get("is_read", 0))
        d["read_at"] = normalize_iso_utc(deliv["read_at"]) if deliv else None

        # If evidence pack references an artifact_id, attach artifact details
        art_id = d["evidence_pack"].get("artifact_id")
        if art_id:
            art_row = await (await db.execute(
                "SELECT id, filename, relative_path, file_size, sha256_hash FROM workspace_artifacts WHERE id = ?",
                (art_id,),
            )).fetchone()
            d["artifact"] = dict(art_row) if art_row else None

        return d


@router.post("/{alert_id}/read")
async def mark_mail_as_read(
    alert_id: int,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Mark this message as read specifically for the calling recipient."""
    now_str = now_iso_utc()

    async with get_db() as db:
        cur = await db.execute(
            """
            UPDATE notification_recipient_deliveries
            SET is_read = 1, read_at = ?
            WHERE alert_id = ? AND (recipient_user_id = ? OR recipient_user_id = 'admin' AND ? = 'sitanshu')
            """,
            (now_str, alert_id, user.user_id, user.user_id),
        )
        if cur.rowcount == 0 and user.role == "administrator":
            await db.execute(
                """
                INSERT INTO notification_recipient_deliveries (
                    alert_id, recipient_email, recipient_user_id, is_read, read_at, created_at
                ) VALUES (?, 'admin@secure.internal', ?, 1, ?, ?)
                """,
                (alert_id, user.user_id, now_str, now_str),
            )

        if user.role == "administrator":
            await db.execute(
                "UPDATE offline_security_alerts SET is_read = 1 WHERE id = ?",
                (alert_id,),
            )

        await db.commit()

    return {"status": "ok", "alert_id": alert_id, "user_id": user.user_id, "is_read": 1}

