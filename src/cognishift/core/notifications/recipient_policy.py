"""Deterministic recipient and sender policy engine for sovereign internal communications.

Ensures that notification recipients and sender identities are dictated strictly
by deterministic security and governance rules, NEVER by non-deterministic LLM output.
"""
from typing import List, Tuple
from cognishift.core.notifications.schemas import NotificationEvidencePack, NotificationType


# Sovereign internal user registry to email mapping
KNOWN_USER_EMAILS = {
    "sitanshu": "admin@secure.internal",
    "admin": "admin@secure.internal",
    "administrator": "admin@secure.internal",
    "zara": "zara@secure.internal",
    "rakshita": "rakshita@secure.internal",
    "rohit": "rohit@secure.internal",
    "vicky": "vicky@secure.internal",
    "aryan": "aryan@secure.internal",
    "operator": "operator@secure.internal",
}

ALL_SUPERVISORS = ["zara@secure.internal", "rakshita@secure.internal"]


def resolve_sender_for_event(event_type: NotificationType) -> str:
    """Determine the authoritative internal sender identity."""
    if event_type in (
        NotificationType.UNTRUSTED_DEVICE,
        NotificationType.NETWORK_DRIFT,
        NotificationType.FOREIGN_NETWORK_OBSERVED,
        NotificationType.DEVICE_BLOCKED,
        NotificationType.DEVICE_REVOKED,
    ):
        return "security-bot@secure.internal"
    elif event_type in (
        NotificationType.SENSITIVE_ACTION_REQUESTED,
        NotificationType.FIRST_SUPERVISOR_APPROVAL,
        NotificationType.FOUR_EYES_COMPLETED,
        NotificationType.ACCESS_AUTHORIZATION,
        NotificationType.AUTHORIZATION_CONSUMED,
    ):
        return "governance-bot@secure.internal"
    else:
        return "system-bot@secure.internal"


def resolve_recipients_for_event(evidence: NotificationEvidencePack) -> List[str]:
    """Determine the deterministic list of recipient mailboxes for this event."""
    event_type = evidence.event_type

    # 1. Device Security & Network Telemetry Events -> Administrator SOC
    if event_type in (
        NotificationType.UNTRUSTED_DEVICE,
        NotificationType.NETWORK_DRIFT,
        NotificationType.FOREIGN_NETWORK_OBSERVED,
        NotificationType.DEVICE_BLOCKED,
        NotificationType.DEVICE_REVOKED,
        NotificationType.RUN_FAILED,
        NotificationType.TEST_ALERT,
    ):
        return ["admin@secure.internal"]

    # 2. Sensitive Action Requested -> Both Supervisors for 4-Eyes Review
    if event_type == NotificationType.SENSITIVE_ACTION_REQUESTED:
        return list(ALL_SUPERVISORS)

    # 3. First Supervisor Approval Recorded -> Remaining Reviewer
    if event_type == NotificationType.FIRST_SUPERVISOR_APPROVAL:
        sup1 = (evidence.supervisor_1 or "").lower()
        if sup1 == "zara":
            return ["rakshita@secure.internal"]
        elif sup1 == "rakshita":
            return ["zara@secure.internal"]
        else:
            return list(ALL_SUPERVISORS)

    # 4. Four-Eyes Authorization Completed -> Operator + Both Supervisors
    if event_type == NotificationType.FOUR_EYES_COMPLETED:
        recipients = set(ALL_SUPERVISORS)
        op = (evidence.target_user or evidence.actor_id or "operator").lower()
        op_email = KNOWN_USER_EMAILS.get(op, f"{op}@secure.internal")
        recipients.add(op_email)
        return sorted(list(recipients))

    # 5. Work Permit Issued or Consumed -> Target Operator + Both Supervisors + Admin
    if event_type in (NotificationType.ACCESS_AUTHORIZATION, NotificationType.AUTHORIZATION_CONSUMED):
        recipients = set(ALL_SUPERVISORS)
        recipients.add("admin@secure.internal")
        op = (evidence.target_user or evidence.actor_id or "operator").lower()
        op_email = KNOWN_USER_EMAILS.get(op, f"{op}@secure.internal")
        recipients.add(op_email)
        return sorted(list(recipients))

    # 6. Artifact Completed -> Requesting Operator & SOC Admin
    if event_type == NotificationType.ARTIFACT_COMPLETED:
        recipients = {"admin@secure.internal"}
        op = (evidence.target_user or evidence.actor_id or "operator").lower()
        op_email = KNOWN_USER_EMAILS.get(op, f"{op}@secure.internal")
        recipients.add(op_email)
        return sorted(list(recipients))

    # Default fallback
    return ["admin@secure.internal"]


def evaluate_routing_policy(evidence: NotificationEvidencePack) -> Tuple[str, List[str]]:
    """Return (sender, recipients) pair for the evidence pack."""
    sender = resolve_sender_for_event(evidence.event_type)
    recipients = resolve_recipients_for_event(evidence)
    return sender, recipients
