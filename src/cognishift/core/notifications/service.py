"""High-level sovereign notification dispatch service.

Orchestrates evidence validation, deterministic routing, composer invocation,
SQLite persistence, and local SMTP transport.
"""
import asyncio
import logging
from typing import Optional, Tuple

from cognishift.core.notifications.composer import compose_notification
from cognishift.core.notifications.outbox import persist_and_deliver_notification
from cognishift.core.notifications.recipient_policy import evaluate_routing_policy
from cognishift.core.notifications.schemas import (
    ComposedNotification,
    NotificationEvidencePack,
)
from cognishift.core.notifications.validator import validate_citations

logger = logging.getLogger(__name__)


async def dispatch_notification_for_event(
    evidence: NotificationEvidencePack,
    dedup_window_seconds: int = 15,
) -> Tuple[int, ComposedNotification, bool]:
    """Execute end-to-end notification pipeline for a verified evidence pack."""
    try:
        # 1. Authoritative Recipient and Sender Resolution
        sender, recipients = evaluate_routing_policy(evidence)

        # 2. Fail-Closed Citation Validation
        if evidence.citations:
            validated_cits, _ = await validate_citations(evidence.citations, strip_invalid=False)
            evidence.citations = validated_cits

        # 3. Notification Composition (Local Model with Deterministic Fallback)
        composed = await compose_notification(
            evidence=evidence,
            sender=sender,
            recipients=recipients,
        )

        # 4. Persistence to SQLite & Delivery via Local SMTP
        alert_id, delivered = await persist_and_deliver_notification(
            composed=composed,
            dedup_window_seconds=dedup_window_seconds,
        )

        logger.info(
            f"Notification [{composed.event_type.value}] dispatch complete. "
            f"Alert #{alert_id}, delivered={delivered}, mode={composed.composition_mode}"
        )
        return alert_id, composed, delivered

    except Exception as exc:
        logger.error(f"Error during notification dispatch for event {evidence.event_type}: {exc}", exc_info=True)
        # Notifications never compromise primary security: return synthetic fallback if critically failed
        raise


def fire_and_forget_notification(evidence: NotificationEvidencePack) -> None:
    """Schedule notification dispatch on the active event loop in the background."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(dispatch_notification_for_event(evidence))
    except RuntimeError:
        # No running loop, run in thread or log
        logger.warning(f"No running event loop to schedule notification for {evidence.event_type}")
