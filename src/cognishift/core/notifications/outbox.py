"""Persistent notification outbox and SQLite storage engine.

Manages durable queuing, deduplication, alert record persistence,
and non-blocking dispatch to the local loopback SMTP transport.
"""
import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

from cognishift.app.db.database import get_db
from cognishift.core.notifications.schemas import ComposedNotification
from cognishift.core.notifications.smtp_transport import send_internal_email

logger = logging.getLogger(__name__)


def generate_dedup_key(composed: ComposedNotification, window_seconds: int = 15) -> str:
    """Generate a coarse time-bucketed deduplication key to prevent alert storms."""
    ev = composed.evidence_pack
    bucket = int(time.time() // window_seconds)
    raw = f"{ev.event_type.value}:{ev.target_user or ''}:{ev.device_id or ''}:{ev.client_ip or ''}:{ev.run_id or ''}:{bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def persist_and_deliver_notification(
    composed: ComposedNotification,
    dedup_window_seconds: int = 15,
) -> Tuple[int, bool]:
    """Persist notification to SQLite (alerts & citations) and deliver via local SMTP.

    Returns:
        (alert_id, delivery_success)
    """
    ev = composed.evidence_pack
    dedup_key = generate_dedup_key(composed, dedup_window_seconds)

    async with get_db() as db:
        # Check deduplication in outbox
        existing = await (await db.execute(
            "SELECT id, status FROM notification_outbox WHERE dedup_key = ?",
            (dedup_key,),
        )).fetchone()
        if existing:
            logger.info(f"Duplicate notification suppressed by dedup key {dedup_key[:12]}")
            return existing["id"], True

        # Insert into offline_security_alerts
        cursor = await db.execute(
            """
            INSERT INTO offline_security_alerts (
                alert_type, severity, subject, sender, recipients,
                body_text, body_html, composition_mode, evidence_pack_json,
                related_user, related_ip, related_device_id, related_run_id, is_read
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                composed.event_type.value,
                composed.severity.value,
                composed.subject,
                composed.sender,
                json.dumps(composed.recipients),
                composed.body_text,
                composed.body_html,
                composed.composition_mode,
                composed.evidence_pack.model_dump_json(),
                ev.target_user,
                ev.client_ip,
                ev.device_id,
                ev.run_id,
            ),
        )
        alert_id = cursor.lastrowid

        # Insert validated citations
        for cit in composed.citations:
            await db.execute(
                """
                INSERT INTO notification_citations (
                    alert_id, citation_index, citation_class, display_label,
                    source_id, page_number, validated, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert_id,
                    cit.citation_index,
                    cit.citation_type.value,
                    cit.display_label,
                    str(cit.source_id),
                    cit.page_number,
                    1 if cit.validated else 0,
                    json.dumps(cit.metadata or {}),
                ),
            )

        # Queue in notification_outbox
        await db.execute(
            """
            INSERT INTO notification_outbox (
                dedup_key, event_type, status, evidence_json
            ) VALUES (?, ?, 'pending', ?)
            """,
            (dedup_key, composed.event_type.value, composed.evidence_pack.model_dump_json()),
        )
        await db.commit()

    # Deliver via loopback SMTP (asynchronously, without blocking caller)
    smtp_ok = await send_internal_email(
        sender=composed.sender,
        recipients=composed.recipients,
        subject=composed.subject,
        body_text=composed.body_text,
        body_html=composed.body_html,
    )

    # Update outbox status
    async with get_db() as db:
        if smtp_ok:
            await db.execute(
                "UPDATE notification_outbox SET status = 'sent', sent_at = CURRENT_TIMESTAMP WHERE dedup_key = ?",
                (dedup_key,),
            )
        else:
            await db.execute(
                "UPDATE notification_outbox SET status = 'failed', error_message = 'SMTP dispatch failed' WHERE dedup_key = ?",
                (dedup_key,),
            )
        await db.commit()

    return alert_id, smtp_ok
