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


class EvidenceCriticality(str, Enum):
    REQUIRED_CRITICAL = "REQUIRED_CRITICAL"
    REQUIRED_SUPPORTING = "REQUIRED_SUPPORTING"
    OPTIONAL = "OPTIONAL"


class EvidenceRequirement(BaseModel):
    role: EvidenceRole
    criticality: EvidenceCriticality = EvidenceCriticality.REQUIRED_CRITICAL
    description: str = ""
    replacement_roles: List[EvidenceRole] = Field(default_factory=list)


class EvidenceLocator(BaseModel):
    kind: str = "page"  # "page", "spreadsheet", "row_range", "document_section", "topology_node"
    document_type: str = "pdf"  # "pdf", "xlsx", "docx", "csv", "topology"
    filename: str
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    row_start: Optional[int] = None
    row_end: Optional[int] = None
    col_start: Optional[str] = None
    col_end: Optional[str] = None
    section_heading: Optional[str] = None
    node_id: Optional[str] = None
    raw_locator: str = ""

    def format_location(self) -> str:
        """Returns the physical coordinates without filename or channel semantics."""
        if self.kind == "spreadsheet" or self.document_type in ("xlsx", "xlsm") or self.sheet_name:
            r_str = f"Rows {self.row_start}-{self.row_end}" if (self.row_start is not None and self.row_end is not None) else ""
            c_str = f"Cols {self.col_start}:{self.col_end}" if (self.col_start and self.col_end) else ""
            parts = [f"Sheet: {self.sheet_name}" if self.sheet_name else None, r_str or None, c_str or None]
            return " | ".join(filter(None, parts)) or "Sheet"
        elif self.kind == "row_range" or self.document_type == "csv":
            if self.row_start is not None and self.row_end is not None:
                return f"Rows {self.row_start}-{self.row_end}"
            return "Rows"
        elif self.kind == "document_section" or (self.document_type == "docx" and self.section_heading):
            p_str = f"Rendered Page {self.page_number}" if self.page_number else ""
            parts = [f"Section: {self.section_heading}", p_str or None]
            return " | ".join(filter(None, parts))
        elif self.page_number is not None:
            return f"Page {self.page_number}"
        return ""

    def format_locator(self, retrieval_channel: Optional[str] = None) -> str:
        """Formats native physical document location coordinates with retrieval channel specification."""
        ch_label = (retrieval_channel or "").upper()
        loc = self.format_location()

        if self.kind == "spreadsheet" or self.document_type in ("xlsx", "xlsm") or self.sheet_name:
            if ch_label:
                return f"[{self.filename} | {loc} | {ch_label}]" if loc else f"[{self.filename} | {ch_label}]"
            return f"[{self.filename} | {loc}]" if loc else f"[{self.filename}]"
        elif self.kind == "row_range" or self.document_type == "csv":
            if ch_label and ch_label not in ("CSV", "TABULAR", "TEXT"):
                return f"[{self.filename} | {loc} | {ch_label}]" if loc else f"[{self.filename} | {ch_label}]"
            return f"[{self.filename} | {loc}]" if loc else f"[{self.filename}]"
        elif self.kind == "document_section" or (self.document_type == "docx" and self.section_heading):
            if ch_label:
                return f"[{self.filename} | {loc} | {ch_label}]" if loc else f"[{self.filename} | {ch_label}]"
            return f"[{self.filename} | {loc}]" if loc else f"[{self.filename}]"
        elif self.page_number is not None:
            if ch_label and ch_label not in ("PDF", "TEXT"):
                return f"[{self.filename} | Page {self.page_number} | {ch_label}]"
            return f"[{self.filename} | Page {self.page_number}]"
        if ch_label and ch_label not in ("PDF", "TEXT"):
            return f"[{self.filename} | {ch_label}]"
        return f"[{self.filename}]"


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


class TruthOrigin(str, Enum):
    DOCUMENT_EVIDENCE = "DOCUMENT_EVIDENCE"
    VERIFIED_VISUAL_OBSERVATION = "VERIFIED_VISUAL_OBSERVATION"
    DATABASE_RECORD = "DATABASE_RECORD"
    DETERMINISTIC_DERIVATION = "DETERMINISTIC_DERIVATION"
    REAL_SANDBOX_EXECUTION = "REAL_SANDBOX_EXECUTION"
    SIMULATED_ADAPTER = "SIMULATED_ADAPTER"
    USER_REPORTED = "USER_REPORTED"
    MODEL_INFERENCE = "MODEL_INFERENCE"


class ObservationQualityStatus(str, Enum):
    VERIFIED = "VERIFIED"
    OBSERVED_UNCORROBORATED = "OBSERVED_UNCORROBORATED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    VLM_FAILED = "VLM_FAILED"
    NO_OBSERVATION = "NO_OBSERVATION"
    RASTERIZATION_FAILED = "RASTERIZATION_FAILED"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"


class ClaimSupportStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ClaimRecord(BaseModel):
    claim_id: str
    claim_type: str = "observation"  # "observation", "spatial_relation", "causal_link", "trip_sequence", "procedural"
    text: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    support_status: ClaimSupportStatus = ClaimSupportStatus.UNSUPPORTED
    confidence: float = 1.0
    origin: TruthOrigin = TruthOrigin.DOCUMENT_EVIDENCE
    provenance: Optional[Dict[str, Any]] = None


class VisualCandidate(BaseModel):
    workspace_id: int
    source_id: int
    processing_version: str = "v1"
    filename: str
    page_number: int
    retrieval_score: float = 0.0
    retrieval_query: str = ""
    expected_role_hint: Optional[str] = None


class VerifiedVisualEvidence(BaseModel):
    evidence_id: str
    source_id: int
    processing_version: str = "v1"
    filename: str
    page_number: int
    evidence_role: EvidenceRole = EvidenceRole.P_AND_ID
    retrieval_channel: str = "visual"
    observed_equipment_tags: List[str] = Field(default_factory=list)
    verified_relations: List[Dict[str, Any]] = Field(default_factory=list)
    verified_numeric_claims: List[Dict[str, Any]] = Field(default_factory=list)
    inspection_status: str = "SUCCESS"
    quality_status: ObservationQualityStatus = ObservationQualityStatus.VERIFIED
    locator: Optional[EvidenceLocator] = None


class ChannelExecutionHealth(BaseModel):
    enabled_channels: List[str] = Field(default_factory=list)
    attempted_channels: List[str] = Field(default_factory=list)
    successful_channels: List[str] = Field(default_factory=list)
    contributing_channels: List[str] = Field(default_factory=list)
    failed_channels: List[str] = Field(default_factory=list)
    requested_channels: List[str] = Field(default_factory=list)
    executed_channels: List[str] = Field(default_factory=list)
    degradation_reason: Optional[str] = None
    hybrid_status: str = "ACTIVE"  # "ACTIVE", "DEGRADED", "DISABLED"
    text_status: str = "ACTIVE"
    visual_status: str = "DISABLED"  # "ACTIVE", "DISABLED", "ERROR"
    visual_model: Optional[str] = None
    visual_device: Optional[str] = None
    visual_pages_indexed: int = 0
    topology_status: str = "EMPTY"  # "ACTIVE", "EMPTY"
    vlm_status: str = "UNAVAILABLE"  # "ACTIVE", "UNAVAILABLE"
    vlm_execution_status: str = "NOT_ATTEMPTED"  # "NOT_ATTEMPTED", "EXECUTED_SUCCESS", "EXECUTED_FAILED"
    text_candidate_count: int = 0
    visual_candidate_count: int = 0
    visual_inspector_executed: bool = False
    visual_inspection_count: int = 0
    topology_node_count: int = 0
    topology_edge_count: int = 0


class StructuredSpatialRelation(BaseModel):
    subject: str  # e.g. "FV-302"
    relation_type: str  # e.g. "UPSTREAM_OF", "DOWNSTREAM_OF", "FEEDS_INTO"
    object: str  # e.g. "R-301"
    supporting_evidence_id: str  # e.g. "E4"
    source_id: Optional[int] = None
    filename: str = ""
    processing_version: str = "v1"
    locator: str = ""
    inspection_status: str = "SUCCESS"
    quality_status: ObservationQualityStatus = ObservationQualityStatus.VERIFIED
    tag_corroboration: bool = False


class ConfirmedObservationItem(BaseModel):
    claim_id: Optional[str] = None
    text: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)


class StructuredRCAResult(BaseModel):
    status: str
    primary_cause_code: str
    primary_cause_text: str = ""
    primary_cause_supporting_evidence_ids: List[str] = Field(default_factory=list)
    confirmed_observations: List[ConfirmedObservationItem] = Field(default_factory=list)
    spatial_relations: List[StructuredSpatialRelation] = Field(default_factory=list)
    claims: List[ClaimRecord] = Field(default_factory=list)
    evidence_items: List[Dict[str, Any]] = Field(default_factory=list)
    channel_health: Optional[ChannelExecutionHealth] = None
    contradictions: List[str] = Field(default_factory=list)
    additional_evidence_needed: List[str] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    outcome_match: Optional[bool] = None
    evidence_chain_valid: Optional[bool] = None
    scenario_pass: Optional[bool] = None


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
    criticality: EvidenceCriticality = EvidenceCriticality.REQUIRED_SUPPORTING
    locator: Optional[EvidenceLocator] = None
    timestamp: Optional[str] = None
    equipment_ids: List[str] = Field(default_factory=list)
    sensor_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RCAEvidenceBundle(BaseModel):
    asset_ids: List[str] = Field(default_factory=list)
    required_roles: List[EvidenceRole] = Field(default_factory=list)
    optional_roles: List[EvidenceRole] = Field(default_factory=list)
    evidence_requirements: List[EvidenceRequirement] = Field(default_factory=list)
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
    stage_latencies_ms: Dict[str, float] = Field(default_factory=dict)

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
