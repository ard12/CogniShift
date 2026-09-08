"""REST APIs for Role-Scoped Sovereign Internal Mailbox.

Domain prefix: /api/v1/mail
Provides role-scoped email client endpoints:
- Operators: view only emails addressed to their own user identity
- Supervisors: view own emails + governance / approval notifications
- Administrators: view full SOC security, system, and governance feeds
- Independent per-recipient read tracking via notification_recipient_deliveries
- Lightweight metadata listing to prevent memory/payload bloat
"""
import asyncio
import json
import logging
import socket
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from cognishift.app.config import settings
from cognishift.app.core.auth import User, get_current_user
from cognishift.app.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mail", tags=["Mailbox"])


def normalize_iso_utc(ts_str: Optional[str]) -> str:
    """Normalize SQLite timestamp string into ISO-8601 UTC with Z suffix."""
    if not ts_str:
        return ""
    ts = str(ts_str).strip()
    if not ts.endswith("Z") and not ("+" in ts[10:] or "-" in ts[10:]):
        return ts.replace(" ", "T") + "Z"
    return ts


@router.get("")
async def list_mailbox_messages(
    limit: int = 50,
    offset: int = 0,
    folder: Optional[str] = None,  # "all", "permits", "security", "governance"
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve role-scoped message list metadata. Full body/citations are excluded for performance."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    async with get_db() as db:
        query_parts: List[str] = []
        params: List[Any] = []

        if user.role == "administrator":
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
            query_parts.append("AND a.alert_type IN ('UNTRUSTED_DEVICE', 'NETWORK_DRIFT', 'FOREIGN_NETWORK_OBSERVED', 'DEVICE_BLOCKED', 'DEVICE_REVOKED')")
        elif folder == "governance":
            query_parts.append("AND a.alert_type IN ('SENSITIVE_ACTION_REQUESTED', 'FIRST_SUPERVISOR_APPROVAL', 'FOUR_EYES_COMPLETED', 'ACCESS_AUTHORIZATION')")

        filter_sql = " ".join(query_parts)

        # Unread count
        if user.role == "administrator":
            unread_sql = f"SELECT count(*) as unread {base_sql} {filter_sql} AND (COALESCE(d.is_read, a.is_read, 0) = 0)"
        else:
            unread_sql = f"SELECT count(*) as unread {base_sql} {filter_sql} AND (COALESCE(d.is_read, 0) = 0)"
        unread_row = await (await db.execute(unread_sql, tuple(params))).fetchone()
        unread_count = unread_row["unread"] if unread_row else 0

        # Total count
        total_sql = f"SELECT count(*) as total {base_sql} {filter_sql}"
        total_row = await (await db.execute(total_sql, tuple(params))).fetchone()
        total_count = total_row["total"] if total_row else 0

        # Select lightweight metadata
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


@router.get("/smtp-health")
async def get_smtp_health() -> Dict[str, Any]:
    """Verify health and reachability of the local loopback SMTP listener."""
    from cognishift.core.notifications.smtp_transport import check_smtp_health
    return await check_smtp_health()


@router.get("/{alert_id}")
async def get_mail_detail(
    alert_id: int,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve full email details including HTML body, text, and verified citations."""
    async with get_db() as db:
        # Access control: verify user has a delivery record or is admin
        if user.role != "administrator":
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

        row = await (await db.execute(
            "SELECT * FROM offline_security_alerts WHERE id = ?",
            (alert_id,),
        )).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Mail message not found.")

        # Read delivery state for this caller
        deliv = await (await db.execute(
            "SELECT is_read, read_at FROM notification_recipient_deliveries WHERE alert_id = ? AND recipient_user_id = ?",
            (alert_id, user.user_id),
        )).fetchone()

        citations = await (await db.execute(
            "SELECT * FROM notification_citations WHERE alert_id = ? ORDER BY citation_index ASC",
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
        d["created_at"] = normalize_iso_utc(d.get("created_at"))
        d["is_read"] = deliv["is_read"] if deliv else d.get("is_read", 0)
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
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    async with get_db() as db:
        # Update user's specific delivery row
        cur = await db.execute(
            """
            UPDATE notification_recipient_deliveries
            SET is_read = 1, read_at = ?
            WHERE alert_id = ? AND (recipient_user_id = ? OR recipient_user_id = 'admin' AND ? = 'sitanshu')
            """,
            (now_str, alert_id, user.user_id, user.user_id),
        )
        if cur.rowcount == 0 and user.role == "administrator":
            # If admin and row wasn't present, create it
            await db.execute(
                """
                INSERT INTO notification_recipient_deliveries (
                    alert_id, recipient_email, recipient_user_id, is_read, read_at, created_at
                ) VALUES (?, 'admin@secure.internal', ?, 1, ?, ?)
                """,
                (alert_id, user.user_id, now_str, now_str),
            )

        # Also update global alert table is_read if admin
        if user.role == "administrator":
            await db.execute(
                "UPDATE offline_security_alerts SET is_read = 1 WHERE id = ?",
                (alert_id,),
            )

        await db.commit()

    return {"status": "ok", "alert_id": alert_id, "user_id": user.user_id, "is_read": 1}


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
    """Purge alerts and recipient deliveries (Administrator only)."""
    if user.role != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")

    async with get_db() as db:
        await db.execute("DELETE FROM notification_citations")
        await db.execute("DELETE FROM notification_recipient_deliveries")
        del_a = await db.execute("DELETE FROM offline_security_alerts")
        count = del_a.rowcount
        await db.commit()

    return {"status": "cleared", "deleted_count": count}
