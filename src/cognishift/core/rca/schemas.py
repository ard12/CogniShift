"""Typed Schemas and Evidence Data Models for CogniShift Root Cause Analysis (RCA)."""
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class EvidenceRole(str, Enum):
    INCIDENT_CHRONOLOGY = "INCIDENT_CHRONOLOGY"
    LIVE_TELEMETRY = "LIVE_TELEMETRY"
    HISTORICAL_TELEMETRY = "HISTORICAL_TELEMETRY"
    VIBRATION = "VIBRATION"
    PRESSURE = "PRESSURE"
    TEMPERATURE = "TEMPERATURE"
    INSPECTION = "INSPECTION"
    MAINTENANCE = "MAINTENANCE"
    SOP_BASELINE = "SOP_BASELINE"
    P_AND_ID = "P_AND_ID"
    TOPOLOGY = "TOPOLOGY"
    RISK_HAZOP = "RISK_HAZOP"
    OTHER = "OTHER"


class RCAStatus(str, Enum):
    CONFIRMED_CAUSE = "CONFIRMED_CAUSE"
    SUPPORTED_LIKELY_CAUSE = "SUPPORTED_LIKELY_CAUSE"
    PLAUSIBLE_HYPOTHESIS = "PLAUSIBLE_HYPOTHESIS"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    ASSET_NOT_FOUND = "ASSET_NOT_FOUND"


class PrimaryCauseCode(str, Enum):
    SUCTION_STARVATION_CAVITATION = "SUCTION_STARVATION_CAVITATION"
    BEARING_OVERHEAT = "BEARING_OVERHEAT"
    VALVE_STEM_BINDING = "VALVE_STEM_BINDING"
    LUBE_OIL_PRESSURE_LOSS = "LUBE_OIL_PRESSURE_LOSS"
    PROCESS_OVERPRESSURE = "PROCESS_OVERPRESSURE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    ASSET_NOT_FOUND = "ASSET_NOT_FOUND"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
    UNKNOWN = "UNKNOWN"


class ChannelExecutionHealth(BaseModel):
    requested_channels: List[str] = Field(default_factory=list)
    executed_channels: List[str] = Field(default_factory=list)
    failed_channels: List[str] = Field(default_factory=list)
    degradation_reason: Optional[str] = None
    hybrid_status: str = "ACTIVE"  # "ACTIVE", "DEGRADED", "DISABLED"
    text_status: str = "ACTIVE"
    visual_status: str = "DISABLED"  # "ACTIVE", "DISABLED", "ERROR"
    visual_model: Optional[str] = None
    visual_device: Optional[str] = None
    visual_pages_indexed: int = 0
    topology_status: str = "EMPTY"  # "ACTIVE", "EMPTY"
    vlm_status: str = "UNAVAILABLE"  # "ACTIVE", "UNAVAILABLE"
    text_candidate_count: int = 0
    visual_candidate_count: int = 0
    topology_node_count: int = 0
    topology_edge_count: int = 0


class RCAEvidenceItem(BaseModel):
    evidence_id: str  # e.g. "E1", "E2" (stable within run)
    source_type: str  # "pdf", "image", "topology", "telemetry", "ocr"
    workspace_id: int
    source_id: Optional[int] = None
    filename: str
    page_number: Optional[int] = None
    processing_version: Optional[str] = None
    retrieval_channel: str  # "text", "visual", "topology", "telemetry", "vlm"
    evidence_role: EvidenceRole
    content: str
    confidence: float = 1.0
    corroborated: bool = False
    timestamp: Optional[str] = None
    equipment_ids: List[str] = Field(default_factory=list)
    sensor_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RCAEvidenceBundle(BaseModel):
    asset_ids: List[str] = Field(default_factory=list)
    required_roles: List[EvidenceRole] = Field(default_factory=list)
    optional_roles: List[EvidenceRole] = Field(default_factory=list)
    evidence_items: List[RCAEvidenceItem] = Field(default_factory=list)
    missing_required_roles: List[EvidenceRole] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    source_coverage: Dict[str, bool] = Field(default_factory=dict)
    modality_coverage: Dict[str, bool] = Field(default_factory=dict)
    telemetry_coverage: Dict[str, bool] = Field(default_factory=dict)
    retrieval_diagnostics: Dict[str, Any] = Field(default_factory=dict)
    channel_health: ChannelExecutionHealth = Field(default_factory=ChannelExecutionHealth)
    final_evidence_channels: List[str] = Field(default_factory=list)
    evidence_channel_counts: Dict[str, int] = Field(default_factory=dict)

    def get_evidence_by_id(self, evidence_id: str) -> Optional[RCAEvidenceItem]:
        for item in self.evidence_items:
            if item.evidence_id == evidence_id:
                return item
        return None

    def format_for_reasoning_prompt(self) -> str:
        """Formats evidence items into structured E-ID blocks for the reasoning LLM."""
        if not self.evidence_items:
            return "No verified documentary or physical telemetry evidence retrieved for this asset."
        lines = ["### AUTHORITATIVE RETRIEVED EVIDENCE (Reference using [E1], [E2], etc.):"]
        for item in self.evidence_items:
            source_loc = item.filename
            if item.page_number:
                source_loc += f" (Page {item.page_number})"
            corr_tag = " [CORROBORATED]" if item.corroborated else ""
            lines.append(
                f"- **[{item.evidence_id}]** [{item.evidence_role.value}] {source_loc}{corr_tag} (Channel: {item.retrieval_channel}):\n"
                f"  {item.content.strip()}"
            )
        if self.missing_required_roles:
            lines.append("\n### MISSING EVIDENCE ROLES:")
            for mr in self.missing_required_roles:
                lines.append(f"- Missing: {mr.value}")
        return "\n".join(lines)


class RCAObservationClaim(BaseModel):
    claim: str
    evidence_ids: List[str] = Field(default_factory=list)


class RCACandidateCause(BaseModel):
    claim: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    status: str = "PLAUSIBLE"  # "SUPPORTED", "PLAUSIBLE", "CONTRADICTED", "UNSUPPORTED"


class RCAPrimaryConclusion(BaseModel):
    claim: str
    evidence_ids: List[str] = Field(default_factory=list)
    status: RCAStatus = RCAStatus.INSUFFICIENT_EVIDENCE
    primary_cause_code: Optional[PrimaryCauseCode] = None


class RCAStructuredResponse(BaseModel):
    status: RCAStatus
    primary_cause_code: Optional[PrimaryCauseCode] = None
    confirmed_observations: List[RCAObservationClaim] = Field(default_factory=list)
    causal_chain: List[str] = Field(default_factory=list)
    candidate_causes: List[RCACandidateCause] = Field(default_factory=list)
    primary_conclusion: RCAPrimaryConclusion
    missing_evidence: List[str] = Field(default_factory=list)
    recommended_checks: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
