"""Pydantic schemas and enums for sovereign security notifications and citations."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class NotificationType(str, Enum):
    UNTRUSTED_DEVICE = "UNTRUSTED_DEVICE"
    NETWORK_DRIFT = "NETWORK_DRIFT"
    FOREIGN_NETWORK_OBSERVED = "FOREIGN_NETWORK_OBSERVED"
    DEVICE_BLOCKED = "DEVICE_BLOCKED"
    DEVICE_REVOKED = "DEVICE_REVOKED"
    SENSITIVE_ACTION_REQUESTED = "SENSITIVE_ACTION_REQUESTED"
    FIRST_SUPERVISOR_APPROVAL = "FIRST_SUPERVISOR_APPROVAL"
    FOUR_EYES_COMPLETED = "FOUR_EYES_COMPLETED"
    CRITICAL_DOCUMENT_FINDING = "CRITICAL_DOCUMENT_FINDING"
    ARTIFACT_COMPLETED = "ARTIFACT_COMPLETED"
    ACCESS_AUTHORIZATION = "ACCESS_AUTHORIZATION"
    AUTHORIZATION_CONSUMED = "AUTHORIZATION_CONSUMED"
    RUN_FAILED = "RUN_FAILED"
    TEST_ALERT = "TEST_ALERT"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CitationClass(str, Enum):
    AUDIT = "AUDIT"
    DEVICE = "DEVICE"
    AUTHENTICATION = "AUTHENTICATION"
    RUN = "RUN"
    APPROVAL = "APPROVAL"
    DOCUMENT = "DOCUMENT"
    DATASET = "DATASET"
    ARTIFACT = "ARTIFACT"
    AUTHORIZATION = "AUTHORIZATION"


class NotificationCitation(BaseModel):
    citation_index: int
    citation_type: CitationClass
    display_label: str
    source_id: str
    page_number: Optional[int] = None
    validated: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(from_attributes=True)


class NotificationEvidencePack(BaseModel):
    event_type: NotificationType
    severity: Severity
    timestamp_iso: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    actor_id: str = "system"
    target_user: Optional[str] = None
    device_id: Optional[str] = None
    device_fingerprint: Optional[str] = None
    client_ip: Optional[str] = None
    previous_ip: Optional[str] = None
    workspace_id: Optional[int] = None
    run_id: Optional[int] = None
    approval_id: Optional[int] = None
    tool_name: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    audit_event_id: Optional[int] = None
    artifact_id: Optional[int] = None
    artifact_name: Optional[str] = None
    artifact_path: Optional[str] = None
    document_name: Optional[str] = None
    document_page: Optional[int] = None
    supervisor_1: Optional[str] = None
    supervisor_2: Optional[str] = None
    permit_code: Optional[str] = None
    correlation_id: Optional[str] = None
    uses_remaining: Optional[int] = None
    summary: str = ""
    citations: List[NotificationCitation] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class ComposedNotification(BaseModel):
    event_type: NotificationType
    severity: Severity
    subject: str
    sender: str
    recipients: List[str]
    body_text: str
    body_html: str
    composition_mode: str = "DETERMINISTIC_TEMPLATE_FALLBACK"
    citations: List[NotificationCitation] = Field(default_factory=list)
    evidence_pack: NotificationEvidencePack
    model_config = ConfigDict(from_attributes=True)
