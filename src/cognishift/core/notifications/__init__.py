"""Sovereign internal security notification package for CogniShift."""
from cognishift.core.notifications.schemas import (
    CitationClass,
    ComposedNotification,
    NotificationCitation,
    NotificationEvidencePack,
    NotificationType,
    Severity,
)
from cognishift.core.notifications.evidence import (
    collect_untrusted_device_evidence,
    collect_network_drift_evidence,
    collect_four_eyes_evidence,
    collect_artifact_evidence,
)
from cognishift.core.notifications.recipient_policy import (
    evaluate_routing_policy,
    resolve_recipients_for_event,
    resolve_sender_for_event,
)
from cognishift.core.notifications.validator import validate_citation, validate_citations
from cognishift.core.notifications.composer import compose_notification
from cognishift.core.notifications.smtp_transport import (
    check_smtp_health,
    send_internal_email,
    start_local_smtp_server,
    stop_local_smtp_server,
)
from cognishift.core.notifications.outbox import flush_pending_outbox
from cognishift.core.notifications.service import (
    dispatch_notification_for_event,
    fire_and_forget_notification,
)

__all__ = [
    "CitationClass",
    "ComposedNotification",
    "NotificationCitation",
    "NotificationEvidencePack",
    "NotificationType",
    "Severity",
    "collect_untrusted_device_evidence",
    "collect_network_drift_evidence",
    "collect_four_eyes_evidence",
    "collect_artifact_evidence",
    "evaluate_routing_policy",
    "resolve_recipients_for_event",
    "resolve_sender_for_event",
    "validate_citation",
    "validate_citations",
    "compose_notification",
    "check_smtp_health",
    "send_internal_email",
    "start_local_smtp_server",
    "stop_local_smtp_server",
    "flush_pending_outbox",
    "dispatch_notification_for_event",
    "fire_and_forget_notification",
]
