"""Deterministic evidence collection helpers for security, governance, and runtime events."""
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from cognishift.core.notifications.schemas import (
    CitationClass,
    NotificationCitation,
    NotificationEvidencePack,
    NotificationType,
    Severity,
)


def collect_untrusted_device_evidence(
    user_id: str,
    device_id: str,
    key_fingerprint: str,
    client_ip: Optional[str] = None,
    audit_event_id: Optional[int] = None,
) -> NotificationEvidencePack:
    """Build an evidence pack for an untrusted device interception."""
    citations: List[NotificationCitation] = []
    idx = 1
    if audit_event_id:
        citations.append(
            NotificationCitation(
                citation_index=idx,
                citation_type=CitationClass.AUDIT,
                display_label=f"Audit Event #{audit_event_id} (Access Blocked)",
                source_id=str(audit_event_id),
                validated=True,
            )
        )
        idx += 1

    citations.append(
        NotificationCitation(
            citation_index=idx,
            citation_type=CitationClass.DEVICE,
            display_label=f"Device Key Fingerprint SHA256:{key_fingerprint[:16]}",
            source_id=device_id,
            validated=True,
            metadata={"fingerprint": key_fingerprint, "ip": client_ip},
        )
    )

    return NotificationEvidencePack(
        event_type=NotificationType.UNTRUSTED_DEVICE,
        severity=Severity.HIGH,
        actor_id=user_id,
        target_user=user_id,
        device_id=device_id,
        device_fingerprint=key_fingerprint,
        client_ip=client_ip,
        audit_event_id=audit_event_id,
        summary=f"Unregistered device connection from user '{user_id}' at IP {client_ip} intercepted with 403 UNKNOWN_DEVICE. Administrator approval required.",
        citations=citations,
    )


def collect_network_drift_evidence(
    user_id: str,
    device_id: str,
    key_fingerprint: str,
    client_ip: str,
    previous_ip: Optional[str] = None,
    is_foreign: bool = False,
    audit_event_id: Optional[int] = None,
) -> NotificationEvidencePack:
    """Build an evidence pack for device network drift or foreign network shift."""
    event_type = NotificationType.FOREIGN_NETWORK_OBSERVED if is_foreign else NotificationType.NETWORK_DRIFT
    severity = Severity.HIGH if is_foreign else Severity.MEDIUM

    citations: List[NotificationCitation] = []
    idx = 1
    if audit_event_id:
        citations.append(
            NotificationCitation(
                citation_index=idx,
                citation_type=CitationClass.AUDIT,
                display_label=f"Audit Record #{audit_event_id}",
                source_id=str(audit_event_id),
                validated=True,
            )
        )
        idx += 1

    citations.append(
        NotificationCitation(
            citation_index=idx,
            citation_type=CitationClass.DEVICE,
            display_label=f"Trusted Device {device_id[:8]}",
            source_id=device_id,
            validated=True,
            metadata={"fingerprint": key_fingerprint},
        )
    )

    summary = (
        f"Trusted device for user '{user_id}' observed from an unexpected network address: {client_ip} "
        f"(previously {previous_ip or 'None'}). Cryptographic key verified; elevated network telemetry logged."
        if is_foreign
        else f"Trusted device for user '{user_id}' observed from a new network address: {client_ip} "
        f"(previously {previous_ip or 'None'}) within the operational network. Normal DHCP shift recorded."
    )

    return NotificationEvidencePack(
        event_type=event_type,
        severity=severity,
        actor_id=user_id,
        target_user=user_id,
        device_id=device_id,
        device_fingerprint=key_fingerprint,
        client_ip=client_ip,
        previous_ip=previous_ip,
        audit_event_id=audit_event_id,
        summary=summary,
        citations=citations,
    )


def collect_four_eyes_evidence(
    event_type: NotificationType,
    run_id: int,
    approval_id: int,
    tool_name: str,
    parameters: Dict[str, Any],
    user_id: str,
    workspace_id: Optional[int] = None,
    supervisor_1: Optional[str] = None,
    supervisor_2: Optional[str] = None,
    audit_event_id: Optional[int] = None,
) -> NotificationEvidencePack:
    """Build an evidence pack for a Four-Eyes governance event."""
    sev = Severity.HIGH if event_type == NotificationType.SENSITIVE_ACTION_REQUESTED else Severity.MEDIUM

    citations: List[NotificationCitation] = [
        NotificationCitation(
            citation_index=1,
            citation_type=CitationClass.RUN,
            display_label=f"Agent Execution Run #{run_id}",
            source_id=str(run_id),
            validated=True,
        ),
        NotificationCitation(
            citation_index=2,
            citation_type=CitationClass.APPROVAL,
            display_label=f"Governance Approval Request #{approval_id}",
            source_id=str(approval_id),
            validated=True,
        ),
    ]

    if audit_event_id:
        citations.append(
            NotificationCitation(
                citation_index=3,
                citation_type=CitationClass.AUDIT,
                display_label=f"Audit Event #{audit_event_id}",
                source_id=str(audit_event_id),
                validated=True,
            )
        )

    summary = ""
    if event_type == NotificationType.SENSITIVE_ACTION_REQUESTED:
        summary = (
            f"Autonomous run #{run_id} attempted sensitive operation '{tool_name}' with parameters {parameters}. "
            f"Execution halted under the Four-Eyes Principle. Dual independent supervisor sign-offs required."
        )
    elif event_type == NotificationType.FIRST_SUPERVISOR_APPROVAL:
        summary = (
            f"Supervisor '{supervisor_1}' approved sensitive tool '{tool_name}' for Run #{run_id}. "
            f"Second independent supervisor approval is now required before execution will resume."
        )
    elif event_type == NotificationType.FOUR_EYES_COMPLETED:
        summary = (
            f"Dual-supervisor Four-Eyes authorization completed for Run #{run_id}. Confirmed by "
            f"'{supervisor_1}' and '{supervisor_2}'. Tool '{tool_name}' executed safely."
        )

    return NotificationEvidencePack(
        event_type=event_type,
        severity=sev,
        actor_id=user_id,
        target_user=user_id,
        workspace_id=workspace_id,
        run_id=run_id,
        approval_id=approval_id,
        tool_name=tool_name,
        parameters=parameters,
        supervisor_1=supervisor_1,
        supervisor_2=supervisor_2,
        audit_event_id=audit_event_id,
        summary=summary,
        citations=citations,
    )


def collect_artifact_evidence(
    run_id: int,
    workspace_id: int,
    user_id: str,
    artifact_id: int,
    artifact_name: str,
    artifact_path: str,
    audit_event_id: Optional[int] = None,
) -> NotificationEvidencePack:
    """Build an evidence pack for an industrial artifact deliverable."""
    citations: List[NotificationCitation] = [
        NotificationCitation(
            citation_index=1,
            citation_type=CitationClass.RUN,
            display_label=f"Execution Run #{run_id}",
            source_id=str(run_id),
            validated=True,
        ),
        NotificationCitation(
            citation_index=2,
            citation_type=CitationClass.ARTIFACT,
            display_label=f"Artifact: {artifact_name}",
            source_id=str(artifact_id),
            validated=True,
            metadata={"path": artifact_path},
        ),
    ]

    return NotificationEvidencePack(
        event_type=NotificationType.ARTIFACT_COMPLETED,
        severity=Severity.LOW,
        actor_id=user_id,
        target_user=user_id,
        workspace_id=workspace_id,
        run_id=run_id,
        artifact_id=artifact_id,
        artifact_name=artifact_name,
        artifact_path=artifact_path,
        audit_event_id=audit_event_id,
        summary=f"Run #{run_id} completed deliverable '{artifact_name}'. Generated artifact stored in workspace #{workspace_id}.",
        citations=citations,
    )
