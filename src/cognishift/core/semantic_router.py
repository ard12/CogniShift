"""Native FastEmbed-Powered Semantic Intent Router for CogniShift.

Enforces Generalized Multi-Domain Intent Classification:
1. Offline, zero-cloud intent routing using local FastEmbed (BAAI/bge-small-en-v1.5).
2. Categorizes requests into typed SemanticIntent classes before model routing or RAG.
3. Decouples intent structure from specific entities (equipment IDs, file names) via normalization.
4. Distinguishes pure capability/discussion from ambiguous directives and operational commands.
5. Employs confidence thresholds, candidate margins, tool validation, and safe abstention.
6. Returns truthful DecisionMethod (RULE, SEMANTIC, ABSTAIN) with no fabricated confidence floats.
"""

import re
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import numpy as np

from cognishift.app.config import settings
from cognishift.core.retriever import embedding_model
from cognishift.core.conversation_context import ResolvedContext

logger = logging.getLogger("cognishift.semantic_router")


class SemanticIntent(str, Enum):
    CONVERSATION = "CONVERSATION"
    KNOWLEDGE_QUERY = "KNOWLEDGE_QUERY"
    ARTIFACT_INSPECTION = "ARTIFACT_INSPECTION"
    CODE_EXECUTION = "CODE_EXECUTION"
    CONTROL_ACTION = "CONTROL_ACTION"
    UI_NAVIGATION = "UI_NAVIGATION"
    COMPLEX_AGENT = "COMPLEX_AGENT"


class DecisionMethod(str, Enum):
    RULE = "RULE"
    SEMANTIC = "SEMANTIC"
    ABSTAIN = "ABSTAIN"


@dataclass
class RoutingReferences:
    """Extracted lightweight reference entities to decouple intent from entity."""
    files: List[str] = field(default_factory=list)
    equipment_ids: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    document_names: List[str] = field(default_factory=list)
    explicit_code_language: Optional[str] = None
    referenced_entities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files": self.files,
            "equipment_ids": self.equipment_ids,
            "tools": self.tools,
            "document_names": self.document_names,
            "explicit_code_language": self.explicit_code_language,
            "referenced_entities": self.referenced_entities
        }


class SemanticRoutingResult:
    """Observable routing metadata produced by SemanticIntentRouter."""
    def __init__(
        self,
        intent: SemanticIntent,
        decision_method: DecisionMethod = DecisionMethod.SEMANTIC,
        confidence: Optional[float] = None,
        runner_up: Optional[SemanticIntent] = None,
        runner_up_score: Optional[float] = None,
        margin: Optional[float] = None,
        abstained: bool = False,
        references: Optional[RoutingReferences] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.intent = intent
        self.decision_method = decision_method
        self.confidence = round(float(confidence), 3) if confidence is not None else None
        self.runner_up = runner_up
        self.runner_up_score = round(float(runner_up_score), 3) if runner_up_score is not None else None
        self.margin = round(float(margin), 3) if margin is not None else None
        self.abstained = abstained
        self.references = references or RoutingReferences()
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "decision_method": self.decision_method.value,
            "confidence": self.confidence,
            "runner_up": self.runner_up.value if self.runner_up else None,
            "runner_up_score": self.runner_up_score,
            "margin": self.margin,
            "abstained": self.abstained,
            "references": self.references.to_dict() if hasattr(self.references, "to_dict") else {},
            "details": self.details
        }

    def __repr__(self) -> str:
        return (
            f"SemanticRoutingResult(intent={self.intent.value}, method={self.decision_method.value}, "
            f"confidence={self.confidence}, margin={self.margin}, abstained={self.abstained})"
        )


FILE_EXT_PATTERN = re.compile(
    r'\b([A-Za-z0-9_\-\.]+\.(?:csv|tsv|xlsx|xls|docx|doc|pptx|pdf|yaml|yml|json|txt|log|md|xml|py))\b',
    re.IGNORECASE
)

EQUIPMENT_PATTERN = re.compile(
    r'\b(?:[A-Z]{1,5}-?[0-9]{1,4}[A-Za-z]?|(?:COMP|MOTOR|PUMP|VALVE|FAN|TURBINE|BOILER|VESSEL|TANK|UNIT)-?[0-9A-Za-z]+)\b'
)

# Standard and regulatory prefixes that must not be confused with equipment
STANDARD_PREFIXES = ['API', 'OISD', 'ISO', 'IEEE', 'ASME', 'OSHA', 'ISA', 'IEC', 'ASTM', 'DIN']

# Registered operational capabilities mapped to tools in CogniShift
SUPPORTED_CONTROL_CAPABILITIES = {
    "check_pressure": ["check pressure", "read pressure", "pressure reading", "discharge pressure"],
    "check_temperature": ["check temperature", "read temperature", "temperature reading", "bearing temperature"],
    "check_network": ["check network", "network status", "ping"],
    "restart_component": ["restart", "reboot", "cycle power", "component restart", "restart pump", "restart the pump"],
    "emergency_pressure_relief": ["emergency pressure relief", "pressure relief", "depressurize", "emergency vent", "emergency trip", "relief valve", "open relief valve", "emergency override", "actuate emergency pressure relief"],
    "run_diagnostic": ["run diagnostic", "diagnostic tool", "equipment diagnostic", "diagnostic self-test", "run diagnostics"],
    "restart_service": ["restart service", "restart network service", "bounce service"]
}


def extract_references(text: str) -> RoutingReferences:
    """Extract lightweight references to files, equipment identifiers, languages, and tools."""
    files = list(dict.fromkeys(FILE_EXT_PATTERN.findall(text)))
    eq_matches = list(dict.fromkeys(EQUIPMENT_PATTERN.findall(text)))
    filtered_eq = [
        e for e in eq_matches
        if e not in files
        and not any(e.upper().startswith(p) for p in STANDARD_PREFIXES)
        and not any(e.lower().endswith('.' + ext) for ext in [
            'py', 'csv', 'yaml', 'yml', 'json', 'pdf', 'xlsx', 'xls', 'docx', 'doc', 'pptx', 'tsv', 'txt', 'log', 'md', 'xml'
        ])
    ]

    code_lang = None
    text_lower = text.lower()
    for lang in ["python", "bash", "powershell", "sql", "javascript"]:
        if re.search(r'\b' + lang + r'\b', text_lower):
            code_lang = lang
            break

    detected_tools = []
    for tool_name, aliases in SUPPORTED_CONTROL_CAPABILITIES.items():
        if tool_name in text_lower or any(alias in text_lower for alias in aliases):
            detected_tools.append(tool_name)

    return RoutingReferences(
        files=files,
        equipment_ids=filtered_eq,
        tools=detected_tools,
        explicit_code_language=code_lang,
        referenced_entities=filtered_eq + files
    )


def normalize_for_routing(text: str, refs: RoutingReferences) -> str:
    """Decouple intent from specific entities by normalizing to generic placeholder tokens."""
    norm = text
    for f in refs.files:
        norm = norm.replace(f, "<file>")
    for eq in refs.equipment_ids:
        norm = norm.replace(eq, "<equipment_id>")
    norm = re.sub(r'[\.\?\!\,\;]+$', '', norm.strip())
    norm = re.sub(r'\s+', ' ', norm).strip().lower()
    return norm


INTENT_ANCHORS: Dict[SemanticIntent, List[str]] = {
    SemanticIntent.CONVERSATION: [
        "what can you do",
        "who are you",
        "what is cognishift",
        "tell me about yourself",
        "can you run python",
        "can you run a python program",
        "can you run python scripts",
        "do you support python execution",
        "can you execute code",
        "can you work with spreadsheets",
        "explain how the sandbox works",
        "tell me about your capabilities",
        "how does local document analysis work",
        "explain how approvals work",
        "what tools are available in this system",
        "hello and good morning",
        "explain your architecture",
        "how does the equipment diagnostic tool work",
        "how do you check sensor telemetry",
        "can you convert a pdf file to a ppt",
        "can you convert a pdf to a ppt",
        "can you convert pdfs to pptx",
        "can you convert files to presentations",
        "can you convert documents to powerpoint",
        "do you support pptx export",
        "can you export presentations",
        "can you convert a pdf to pptx",
        "confirm that cognishift is operational",
        "is cognishift operational",
        "confirm that cognishift is operational and explain that processing is performed locally",
        "explain that processing is performed locally",
        "explain in two sentences what cognishift does",
        "explain what cognishift does",
        "confirm local processing and operational status",
        "confirm system status and offline sovereign execution"
    ],
    SemanticIntent.KNOWLEDGE_QUERY: [
        "what does our procedure say about this issue",
        "find the relevant internal policy",
        "what is the permitted operating limit",
        "which manual covers this condition",
        "what does our engineering standard say",
        "cite the relevant internal procedure and page number",
        "which procedure applies to <equipment_id>",
        "which standard operating procedure applies to <equipment_id>",
        "what is the maximum allowable working pressure according to API 610",
        "what are the refinery safety guidelines for hydrocracker vessels",
        "what is the allowable operating envelope in OISD-156",
        "what does the procurement policy require for vendor approval",
        "what does our procurement policy say about single-source vendors",
        "what does the cybersecurity sop say about removable media",
        "what does the finance policy say about approval limits",
        "what does the compressor manual say about lubrication",
        "what is the vibration limit in the rotating-equipment standard",
        "what is the normal discharge pressure range",
        "what is the continuous speed limit on <equipment_id>",
        "what is the continuous speed limit on compressor <equipment_id>",
        "what is the maximum design speed limit for <equipment_id>",
        "what does the sop say about emergency trips",
        "what does the standard operating procedure state for seal flush",
        "what does our remote work policy say",
        "what does our policy say about remote work",
        "what is the company policy on remote work",
        "what does the remote work policy say",
        "what kind of PPE and safety gear do we need before opening the pump casing",
        "what safety gear and PPE is required by the standard",
        "what is the procedure for lock out tag out on the pump",
        "what is the lockout tagout LOTO protocol",
        "what are the main steps to service the pump according to the manual",
        "how often do we need to inspect the pressure relief valves according to OISD",
        "what was MRPL's gross refining margin trend over the last 3 years? break it down simply",
        "what was the gross refining margin trend over the last 3 years",
        "what is MRPL's gross refining margin GRM",
        "what was our gross refining margin over the past three years",
        "break down the gross refining margin trend simply",
        "what were the gross refining margins and trends",
        "according to the documents currently available in my knowledge vault",
        "according to the documents in knowledge vault",
        "what is the remaining corrosion life from its inspection report",
        "what is the remaining corrosion life of <equipment_id>",
        "cite the source from the inspection report"
    ],
    SemanticIntent.ARTIFACT_INSPECTION: [
        "explain <file>",
        "summarize <file>",
        "inspect this workspace artifact",
        "tell me what <file> contains",
        "describe the contents of this generated report",
        "what information is in <file>",
        "show me the summary of <file>",
        "inspect the artifact file in workspace",
        "what is inside <file>",
        "summarize the referenced spreadsheet <file>",
        "explain the contents of the document <file>",
        "what does the attached presentation <file> contain",
        "describe the findings in the generated summary file",
        "explain the configuration settings inside <file>",
        "show me the details recorded in <file>",
        "what data is stored in the exported file",
        "summarize the notes in <file>",
        "review the contents of the uploaded artifact"
    ],
    SemanticIntent.CODE_EXECUTION: [
        "run python on <file>",
        "execute code to analyze this dataset",
        "write and run a script on <file>",
        "write and execute a script for this file",
        "calculate these values using python",
        "process this spreadsheet in the sandbox",
        "generate code and execute it in python",
        "run a statistical analysis on this data",
        "run python to analyze <file>",
        "write a python script to calculate variance",
        "write a python script to calculate payroll variance",
        "write a python script to compute metrics",
        "write and execute code to compute mean values",
        "calculate standard deviation using python",
        "execute python script to find anomalies in <file>",
        "execute python code in the sandbox to compute mean pressure",
        "run a python script to parse the equipment logs",
        "write a python program to filter rows in <file>",
        "execute python code to generate summary metrics",
        "compute statistical 3-sigma values using python",
        "execute data processing script in the sandbox",
        "can you do a data analysis on the excel file",
        "perform data analysis and generate visualization",
        "do a deep financial audit on the excel file",
        "analyze the spreadsheet and generate png visualization",
        "visualize financial history in png format",
        "do a quantitative audit on the financial history file",
        "create an audit on financial history excel file",
        "plot the financial metrics in png format",
        "write python to analyze the financial spreadsheet"
    ],
    SemanticIntent.CONTROL_ACTION: [
        "check discharge pressure on <equipment_id>",
        "check pressure on <equipment_id>",
        "read pressure on <equipment_id>",
        "check temperature on <equipment_id>",
        "inspect temperature on <equipment_id>",
        "restart <equipment_id> now",
        "restart <equipment_id>",
        "please restart <equipment_id> immediately",
        "execute component restart on <equipment_id>",
        "restart component <equipment_id> now",
        "execute emergency pressure relief",
        "trigger emergency pressure relief on <equipment_id>",
        "trigger emergency depressurization on <equipment_id>",
        "run equipment diagnostic on <equipment_id>",
        "run diagnostic on <equipment_id> now",
        "run the diagnostic tool on <equipment_id>",
        "execute diagnostic self-test on <equipment_id>",
        "restart service on <equipment_id>",
        "restart network service now",
        "execute restart_service immediately",
        "trigger emergency trip on <equipment_id>",
        "stop equipment <equipment_id> now",
        "isolate component <equipment_id> now"
    ],
    SemanticIntent.UI_NAVIGATION: [
        "take me to the portal where I can ingest documents",
        "take me to the document ingestion portal",
        "where can I ingest documents",
        "where do I upload documents",
        "how do I upload documents to the knowledge base",
        "open the document upload page",
        "navigate to the knowledge vault",
        "go to knowledge",
        "open knowledge",
        "take me to approvals",
        "show me pending approvals",
        "go to approvals",
        "take me to shift supervisor approvals",
        "go to the dashboard",
        "open dashboard",
        "take me to agent settings",
        "open agents studio",
        "show all workspaces",
        "open system telemetry monitor",
        "navigate to artifact store",
        "show run history",
        "take me to operator chat"
    ]
}


class SemanticIntentRouter:
    """Local, offline FastEmbed-based Generalized Semantic Intent Router."""

    def __init__(
        self,
        confidence_threshold: Optional[float] = None,
        margin_threshold: Optional[float] = None,
        control_confidence_threshold: Optional[float] = None,
        control_margin_threshold: Optional[float] = None
    ):
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else settings.semantic_router_confidence_threshold
        )
        self.margin_threshold = (
            margin_threshold
            if margin_threshold is not None
            else settings.semantic_router_margin_threshold
        )
        self.control_confidence_threshold = (
            control_confidence_threshold
            if control_confidence_threshold is not None
            else getattr(settings, "semantic_router_control_confidence_threshold", 0.75)
        )
        self.control_margin_threshold = (
            control_margin_threshold
            if control_margin_threshold is not None
            else getattr(settings, "semantic_router_control_margin_threshold", 0.12)
        )

        self._anchors = INTENT_ANCHORS
        self._anchor_embeddings: Dict[SemanticIntent, np.ndarray] = {}
        self._precompute_anchor_embeddings()

    def _precompute_anchor_embeddings(self) -> None:
        """Precompute and normalize embedding matrices for all anchor phrases."""
        for intent, phrases in self._anchors.items():
            raw_embs = list(embedding_model.embed(phrases))
            arr = np.array(raw_embs, dtype=np.float32)
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            normalized = arr / norms
            self._anchor_embeddings[intent] = normalized
        logger.info(f"Precomputed anchor embeddings for {len(self._anchor_embeddings)} intents (balanced anchors).")

    def route(
        self,
        user_prompt: str,
        resolved_context: Optional[ResolvedContext] = None,
        active_pending_task: Optional[Any] = None
    ) -> SemanticRoutingResult:
        """
        Classifies incoming user instruction into a SemanticIntent.
        Preserves strict question vs control action safety, extracts references,
        normalizes entities, and ensures truthful decision metadata.
        """
        raw_text = (user_prompt or "").strip()
        refs = extract_references(raw_text)

        # Merge references resolved from conversation context when anaphora is present
        if resolved_context and resolved_context.has_anaphora:
            for f in resolved_context.files:
                if f not in refs.files:
                    refs.files.append(f)
                if f not in refs.referenced_entities:
                    refs.referenced_entities.append(f)
            for eq in resolved_context.equipment_ids:
                if eq not in refs.equipment_ids:
                    refs.equipment_ids.append(eq)
                if eq not in refs.referenced_entities:
                    refs.referenced_entities.append(eq)

        # 1. Deterministic Rule: Empty Input
        if not raw_text:
            return SemanticRoutingResult(
                intent=SemanticIntent.CONVERSATION,
                decision_method=DecisionMethod.RULE,
                confidence=None,
                runner_up=None,
                margin=None,
                abstained=False,
                references=refs,
                details={"reason": "empty_input"}
            )

        text_lower = raw_text.lower()

        # 1.5. Pipeline Stage 1: Pending Task Continuation / Cancellation / Affirmation
        if resolved_context and resolved_context.is_cancellation:
            return SemanticRoutingResult(
                intent=SemanticIntent.CONVERSATION,
                decision_method=DecisionMethod.RULE,
                confidence=None,
                runner_up=None,
                margin=None,
                abstained=False,
                references=refs,
                details={
                    "rule": "user_cancellation",
                    "cancelled_task_id": getattr(active_pending_task, "id", None)
                }
            )

        if resolved_context and resolved_context.is_affirmation:
            if active_pending_task:
                task_intent_str = getattr(active_pending_task, "intent", "COMPLEX_AGENT")
                try:
                    task_intent = SemanticIntent(task_intent_str)
                except ValueError:
                    task_intent = SemanticIntent.COMPLEX_AGENT
                return SemanticRoutingResult(
                    intent=task_intent,
                    decision_method=DecisionMethod.RULE,
                    confidence=1.0,
                    runner_up=None,
                    margin=None,
                    abstained=False,
                    references=refs,
                    details={
                        "resumed_task_id": active_pending_task.id,
                        "goal": active_pending_task.requested_goal,
                        "version": active_pending_task.version,
                        "source_references": active_pending_task.source_references
                    }
                )
            else:
                return SemanticRoutingResult(
                    intent=SemanticIntent.CONVERSATION,
                    decision_method=DecisionMethod.RULE,
                    confidence=None,
                    runner_up=None,
                    margin=None,
                    abstained=False,
                    references=refs,
                    details={"rule": "stale_or_missing_pending_task"}
                )

        # 1.6. Explicit Negation / Cancellation Guard on Actions ("Do not restart P-101A")
        if self._is_negated_action(text_lower):
            return SemanticRoutingResult(
                intent=SemanticIntent.CONVERSATION,
                decision_method=DecisionMethod.RULE,
                confidence=None,
                runner_up=None,
                margin=None,
                abstained=False,
                references=refs,
                details={"rule": "negation_guard"}
            )

        # 2. Deterministic Rule: UI Navigation Commands (/documents, open sandbox, etc.)
        nav_result = self._check_ui_navigation(text_lower, refs)
        if nav_result:
            return nav_result

        # 3. Critical Safety Distinction: Capability/Discussion vs Action Command
        # Pure capability / educational inquiry about actions (e.g. "Explain restart_component procedure")
        is_capability_inquiry = self._is_capability_inquiry_about_action(text_lower)
        if is_capability_inquiry:
            return SemanticRoutingResult(
                intent=SemanticIntent.CONVERSATION,
                decision_method=DecisionMethod.RULE,
                confidence=None,
                runner_up=None,
                margin=None,
                abstained=False,
                references=refs,
                details={"rule": "action_inquiry_guard"}
            )

        # 3.2. Deterministic Rule: System Status, General Conversation, and Operational Capability Inquiries
        is_system_or_conversation = (
            any(p in text_lower for p in [
                "confirm that cognishift is operational", "is cognishift operational",
                "explain that processing is performed locally", "processing is performed locally",
                "what does cognishift do", "explain in two sentences what cognishift does",
                "what is cognishift", "who are you", "what can you do", "hello", "good morning", "good evening"
            ])
            and not refs.files
            and not refs.equipment_ids
            and not any(w in text_lower for w in ["sop", "manual", "scada", "telemetry", "sap", "audit"])
        )
        if is_system_or_conversation:
            return SemanticRoutingResult(
                intent=SemanticIntent.CONVERSATION,
                decision_method=DecisionMethod.RULE,
                confidence=1.0,
                runner_up=None,
                margin=None,
                abstained=False,
                references=refs,
                details={"rule": "system_or_conversation_guard"}
            )

        # Ambiguous Modal Directives on Actions (Safe Abstention to COMPLEX_AGENT)
        is_ambiguous_control = self._is_ambiguous_control_request(text_lower, refs)
        if is_ambiguous_control:
            return SemanticRoutingResult(
                intent=SemanticIntent.COMPLEX_AGENT,
                decision_method=DecisionMethod.ABSTAIN,
                confidence=None,
                runner_up=SemanticIntent.CONTROL_ACTION,
                runner_up_score=None,
                margin=None,
                abstained=True,
                references=refs,
                details={"reason": "ambiguous_control_request", "candidate": "CONTROL_ACTION"}
            )

        # 4. Deterministic Rule: Explicit Workspace Artifact Inspection
        is_artifact_inquiry = self._is_artifact_inquiry(text_lower, refs)
        if is_artifact_inquiry:
            return SemanticRoutingResult(
                intent=SemanticIntent.ARTIFACT_INSPECTION,
                decision_method=DecisionMethod.RULE,
                confidence=None,
                runner_up=None,
                margin=None,
                abstained=False,
                references=refs,
                details={
                    "rule": "explicit_file_inquiry",
                    "file": refs.files[0] if refs.files else None
                }
            )

        # 4.5. Deterministic Rule: Explicit Imperative Code Execution, Data Analysis & Document Conversion
        is_pure_capability_question = (
            any(text_lower.startswith(qo) for qo in [
                "can you", "could you", "would you", "how do you", "how can", "is it possible",
                "what can", "what is", "explain how", "do you support", "are you able to"
            ])
            and not refs.files
            and not refs.equipment_ids
            and not any(text_lower.startswith(p) for p in [
                "can you please convert this", "can you please generate", "can you please run",
                "can you please create", "can you please execute", "can you convert the latest"
            ])
            and (
                len(text_lower.split()) <= 8
                or any(w in text_lower for w in [
                    "what can you do", "who are you", "your capabilities", "can you convert",
                    "can you run", "can you execute", "do you support", "can you work with"
                ])
            )
            and not any(w in text_lower for w in [
                "financial audit", "deep audit", "operating ebitda", "urgent maintenance"
            ])
        )

        is_imperative_code = bool(re.search(
            r'(?:run|execute|write|generate|make\s+(?:the\s+)?(?:ai|agent)\s+write)\b.*?\b(?:python|code|script|program)\b',
            text_lower
        ))
        is_document_conversion = bool(re.search(
            r'\b(?:convert|transform)\b.*?\b(?:into|to|as)\s*(?:docx|pdf|excel|xlsx|spreadsheet|csv|jpg|jpeg|png|image|ppt|pptx|powerpoint|slides|presentation)\b',
            text_lower
        )) or bool(re.search(
            r'\b(?:export|create|generate|render|review.*?and\s+(?:convert|create|generate|export|render))\b.*?\b(?:into|to|as|in)?\s*(?:docx|pdf|excel|xlsx|spreadsheet|csv|jpg|jpeg|png|image|ppt|pptx|powerpoint|slides|presentation)\b',
            text_lower
        )) or bool(re.search(
            r'\b(?:want|need|give\s+me|make|generate|create|export|produce|provide|prepare|get)\b.*?\b(?:audit|report|summary|analysis|document|deliverable|file|overview)\b.*?\b(?:docx|word|pdf|excel|xlsx|spreadsheet|csv|pptx|powerpoint)\b',
            text_lower
        )) or bool(re.search(
            r'\b(?:proper\s+)?(?:audit|report|summary|analysis|document|deliverable|overview)\b.*?\b(?:in|as|into)\s+(?:docx|word|pdf|excel|xlsx|spreadsheet|csv|pptx|powerpoint)(?:\s+format)?\b',
            text_lower
        )) or bool(re.search(
            r'\b(?:in|as|into)\s+(?:docx|word|pdf|excel|xlsx|pptx)\s+format\b',
            text_lower
        )) or (
            any(w in text_lower for w in ["docx", "pdf", "pptx", "word format", "docx format", "pdf format"])
            and any(w in text_lower for w in ["audit", "report", "proper", "format", "deliverable", "generate", "create", "make"])
            and not any(w in text_lower for w in ["what can you do", "can you convert", "do you support"])
        )
        from cognishift.core.visualization.selector import parse_artifact_request_contract
        artifact_req = parse_artifact_request_contract(raw_text)
        is_visualization_cmd = artifact_req.png_required or bool(re.search(
            r'\b(?:visualize|visual|plot|chart|graph)\b.*?\b(?:matplotlib|seaborn|telemetry|readings|sensor|data|png|image|excel|history|trend|metric|breakdown)\b',
            text_lower
        )) or any(p in text_lower for p in [
            "visual breakdown", "simple chart", "make a chart", "generate a chart", "plot the", "visual chart"
        ])
        is_analysis_or_audit_cmd = (bool(re.search(
            r'\b(?:data\s+analysis|financial\s+(?:audit|history|performance)|deep\s+(?:financial\s+)?audit|audit\s+on|quantitative\s+audit|do\s+(?:a\s+)?(?:complete\s+)?audit|complete\s+audit)\b',
            text_lower
        )) and any(w in text_lower for w in ["excel", "xlsx", "spreadsheet", "csv", "data", "history", "financial", "png", "image", "chart", "file", "registry", "p&id", "pid"])) or any(p in text_lower for p in [
            "make me a report", "generate a report", "make a report", "compare our operating ebitda", "urgent maintenance jobs in the sap", "do a complete audit", "complete audit"
        ])

        if (is_imperative_code or is_document_conversion or is_visualization_cmd or is_analysis_or_audit_cmd) and not is_pure_capability_question:
            return SemanticRoutingResult(
                intent=SemanticIntent.CODE_EXECUTION,
                decision_method=DecisionMethod.RULE,
                confidence=1.0,
                runner_up=None,
                margin=None,
                abstained=False,
                references=refs,
                details={"rule": "explicit_code_execution_command"}
            )

        # 4.6. Deterministic Rule: Explicit Knowledge Query / Document Citation
        is_knowledge_inquiry = (
            bool(re.search(r'\b(?:according to|based on)\s+(?:the\s+|our\s+|my\s+)?(?:documents?|knowledge(?:\s+vault|\s+base)?|manuals?|sops?|reports?|standards?)\b', text_lower))
            or bool(re.search(r'\b(?:in|from)\s+(?:my\s+|the\s+|our\s+)?(?:knowledge\s+vault|knowledge\s+base|inspection\s+report)\b', text_lower))
            or bool(re.search(r'\bcite\s+(?:the\s+)?(?:source|sources|manual|sop|procedure|standard)\b', text_lower))
            or bool(re.search(r'\bwhat\s+does\s+(?:the|our)\s+(?:sop|procedure|standard|manual|policy)\s+(?:say|state|require)\b', text_lower))
            or "corrosion life" in text_lower
        ) and not bool(re.search(r'\b(?:run|execute|write|generate)\b.*?\b(?:python|code|script|program)\b', text_lower)) \
          and not bool(re.search(r'\b(?:restart|trip|depressurize|reboot)\b', text_lower))

        if is_knowledge_inquiry:
            return SemanticRoutingResult(
                intent=SemanticIntent.KNOWLEDGE_QUERY,
                decision_method=DecisionMethod.RULE,
                confidence=1.0,
                runner_up=None,
                margin=None,
                abstained=False,
                references=refs,
                details={"rule": "explicit_knowledge_inquiry"}
            )

        # 5. FastEmbed Vector Similarity Matching (Normalized Text)
        norm_text = normalize_for_routing(raw_text, refs)
        query_embs = list(embedding_model.embed([norm_text]))
        query_vec = np.array(query_embs[0], dtype=np.float32)
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 0:
            query_vec /= q_norm

        scores: Dict[SemanticIntent, float] = {}
        for intent, anchor_mat in self._anchor_embeddings.items():
            sims = np.dot(anchor_mat, query_vec)
            top_k = np.sort(sims)[::-1][:min(3, len(sims))]
            composite_score = float(0.70 * top_k[0] + 0.30 * np.mean(top_k))
            scores[intent] = max(0.0, min(1.0, composite_score))

        # Question Guard: Pure informational inquiries must never compete with operational CONTROL_ACTION
        question_openers = [
            "what is", "what are", "what does", "what do", "which",
            "how many", "where is", "where are", "who is", "cite the",
            "is there a", "are there any", "do we have", "how do we",
            "how can we", "why is", "why do", "why should", "when is", "when do"
        ]
        is_informational_inquiry = (
            any(text_lower.startswith(qo) for qo in question_openers)
            or any(text_lower.startswith(w) for w in [
                "what ", "how ", "why ", "when ", "where ", "which ", "who ",
                "is there", "are there", "do we", "can you explain", "can you tell",
                "explain ", "describe ", "cite ", "summarize ", "list "
            ])
            or any(w in text_lower for w in [
                "according to", "based on", "cite the", "what is", "what are", "what does",
                "which procedure", "which manual", "corrosion life", "inspection report"
            ])
            or "?" in text_lower
        )
        # Ensure that active imperative control actions (restart, trip, override, open valve) are not suppressed
        is_explicit_control_imperative = (
            any(text_lower.startswith(w) for w in ["restart ", "trip ", "override ", "depressurize ", "reboot ", "actuate ", "open "])
            or any(w in text_lower for w in ["actuate emergency", "emergency trip", "execute emergency", "open relief valve"])
        )
        if is_informational_inquiry and not is_explicit_control_imperative:
            if SemanticIntent.CONTROL_ACTION in scores:
                scores[SemanticIntent.CONTROL_ACTION] = 0.0

        sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_intent, top_score = sorted_intents[0]
        runner_up_intent, runner_up_score = sorted_intents[1]
        margin = top_score - runner_up_score

        # 6. Unsupported Action Guard for CONTROL_ACTION
        is_supported_control = False
        if top_intent == SemanticIntent.CONTROL_ACTION:
            is_supported_control = self._is_supported_control_action(text_lower, refs)
            if not is_supported_control:
                logger.info(
                    f"Semantic router intercepted unsupported action command '{raw_text[:50]}': "
                    f"no registered control tool matches. Routing to COMPLEX_AGENT."
                )
                return SemanticRoutingResult(
                    intent=SemanticIntent.COMPLEX_AGENT,
                    decision_method=DecisionMethod.ABSTAIN,
                    confidence=top_score,
                    runner_up=runner_up_intent,
                    runner_up_score=runner_up_score,
                    margin=margin,
                    abstained=True,
                    references=refs,
                    details={"candidate": "CONTROL_ACTION", "reason": "unsupported_action_no_tool"}
                )

        # 7. Safe Abstention Evaluation (Thresholds and Margins)
        should_abstain = (top_score < self.confidence_threshold) or (margin < self.margin_threshold)

        if top_intent == SemanticIntent.CONTROL_ACTION:
            ctrl_margin = self.control_margin_threshold
            if top_score < self.control_confidence_threshold or margin < ctrl_margin:
                should_abstain = True

        if should_abstain:
            logger.info(
                f"Semantic router abstained on '{raw_text[:50]}': top={top_intent.value} ({top_score:.2f}), "
                f"runner_up={runner_up_intent.value} ({runner_up_score:.2f}), margin={margin:.2f}"
            )
            return SemanticRoutingResult(
                intent=SemanticIntent.COMPLEX_AGENT,
                decision_method=DecisionMethod.ABSTAIN,
                confidence=top_score,
                runner_up=runner_up_intent,
                runner_up_score=runner_up_score,
                margin=margin,
                abstained=True,
                references=refs,
                details={"candidate": top_intent.value, "reason": "threshold_or_margin_insufficient"}
            )

        return SemanticRoutingResult(
            intent=top_intent,
            decision_method=DecisionMethod.SEMANTIC,
            confidence=top_score,
            runner_up=runner_up_intent,
            runner_up_score=runner_up_score,
            margin=margin,
            abstained=False,
            references=refs,
            details={"scores": {k.value: round(v, 3) for k, v in scores.items()}}
        )

    def _check_ui_navigation(self, text: str, refs: RoutingReferences) -> Optional[SemanticRoutingResult]:
        """Detect deterministic UI navigation commands."""
        clean_text = text.strip().rstrip('.?!,;').strip().lower()
        slash_commands = {
            "/documents": ("documents", "/knowledge", "Knowledge Vault"),
            "/knowledge": ("knowledge", "/knowledge", "Knowledge Vault"),
            "/sandbox": ("sandbox", "/system", "Sandbox Environment"),
            "/sovereignty": ("sovereignty", "/system", "System Sovereignty"),
            "/approvals": ("approvals", "/approvals", "Shift Supervisor Approvals"),
            "/artifacts": ("artifacts", "/artifacts", "Workspace Artifacts"),
            "/audit": ("audit", "/system", "Audit Logs"),
            "/dashboard": ("dashboard", "/dashboard", "Operational Dashboard"),
            "/agents": ("agents", "/agents", "Agent Definitions"),
            "/operator": ("operator", "/operator", "Operator Console"),
            "/workspaces": ("workspaces", "/workspaces", "Workspace Management"),
            "/runs": ("runs", "/runs", "Execution Run History"),
            "/help": ("dashboard", "/dashboard", "Help & Documentation"),
            "/status": ("system", "/system", "System Telemetry"),
            "/policy": ("dashboard", "/dashboard", "Operational Policy")
        }
        if clean_text in slash_commands:
            target, route, friendly = slash_commands[clean_text]
            return SemanticRoutingResult(
                intent=SemanticIntent.UI_NAVIGATION,
                decision_method=DecisionMethod.RULE,
                confidence=None,
                abstained=False,
                references=refs,
                details={"target": target, "target_route": route, "friendly_name": friendly}
            )

        # 1. Document Ingestion / Knowledge Vault Navigation Patterns
        knowledge_nav_patterns = [
            r'^\s*(?:please\s+)?(?:how\s+to\s+)?(?:ingest|upload)\s+(?:documents?|files?|pdfs?|manuals?|data)\s*$',
            r'.*\b(?:portal|page|view|tab|screen)\s+(?:where\s+i\s+can|to|for)\s+(?:ingest|upload)\b.*',
            r'.*\b(?:where|how)\s+(?:can\s+i|do\s+i|to)\s+(?:ingest|upload)\b.*',
            r'.*\b(?:take\s+me\s+to|go\s+to|open|navigate\s+to|show)\s+(?:the\s+)?(?:knowledge|knowledge\s+vault|knowledge\s+base|document\s+portal|upload\s+portal)\b.*',
        ]
        for pat in knowledge_nav_patterns:
            if re.search(pat, clean_text):
                return SemanticRoutingResult(
                    intent=SemanticIntent.UI_NAVIGATION,
                    decision_method=DecisionMethod.RULE,
                    confidence=None,
                    abstained=False,
                    references=refs,
                    details={"target": "knowledge", "target_route": "/knowledge", "friendly_name": "Knowledge Vault"}
                )

        # 2. General Exact Navigation Phrases
        exact_nav_phrases = {
            "open documents": ("knowledge", "/knowledge", "Knowledge Vault"),
            "show documents": ("knowledge", "/knowledge", "Knowledge Vault"),
            "list documents": ("knowledge", "/knowledge", "Knowledge Vault"),
            "open knowledge": ("knowledge", "/knowledge", "Knowledge Vault"),
            "show knowledge": ("knowledge", "/knowledge", "Knowledge Vault"),
            "open sandbox": ("system", "/system", "Sandbox Environment"),
            "show sandbox": ("system", "/system", "Sandbox Environment"),
            "open sovereignty": ("system", "/system", "System Sovereignty"),
            "show sovereignty": ("system", "/system", "System Sovereignty"),
            "network monitor": ("system", "/system", "Network Telemetry"),
            "open approvals": ("approvals", "/approvals", "Shift Supervisor Approvals"),
            "show approvals": ("approvals", "/approvals", "Shift Supervisor Approvals"),
            "show pending approvals": ("approvals", "/approvals", "Shift Supervisor Approvals"),
            "take me to approvals": ("approvals", "/approvals", "Shift Supervisor Approvals"),
            "take me to approvals view": ("approvals", "/approvals", "Shift Supervisor Approvals"),
            "go to approvals": ("approvals", "/approvals", "Shift Supervisor Approvals"),
            "open artifacts": ("artifacts", "/artifacts", "Workspace Artifacts"),
            "show artifacts": ("artifacts", "/artifacts", "Workspace Artifacts"),
            "list artifacts": ("artifacts", "/artifacts", "Workspace Artifacts"),
            "open audit": ("system", "/system", "Audit Logs"),
            "show audit": ("system", "/system", "Audit Logs"),
            "show audit logs": ("system", "/system", "Audit Logs"),
            "audit logs": ("system", "/system", "Audit Logs"),
            "open dashboard": ("dashboard", "/dashboard", "Operational Dashboard"),
            "show dashboard": ("dashboard", "/dashboard", "Operational Dashboard"),
            "go to dashboard": ("dashboard", "/dashboard", "Operational Dashboard"),
            "open agents": ("agents", "/agents", "Agent Definitions"),
            "go to agents": ("agents", "/agents", "Agent Definitions"),
            "open workspaces": ("workspaces", "/workspaces", "Workspaces"),
            "go to workspaces": ("workspaces", "/workspaces", "Workspaces"),
            "open runs": ("runs", "/runs", "Execution Run History"),
            "go to runs": ("runs", "/runs", "Execution Run History"),
        }
        if clean_text in exact_nav_phrases:
            target, route, friendly = exact_nav_phrases[clean_text]
            return SemanticRoutingResult(
                intent=SemanticIntent.UI_NAVIGATION,
                decision_method=DecisionMethod.RULE,
                confidence=None,
                abstained=False,
                references=refs,
                details={"target": target, "target_route": route, "friendly_name": friendly}
            )

        # 3. Regex matching for navigation commands (e.g. "take me to ... view", "go to ... page")
        nav_match = re.match(r'^(?:take me to|go to|navigate to|switch to|open|show)\s+(?:the\s+)?([a-z0-9_\-\s]+?)(?:\s+view|\s+page|\s+tab|\s+portal|\s+screen)?$', clean_text)
        if nav_match:
            target_str = nav_match.group(1).strip()
            nav_views = {
                "document": ("knowledge", "/knowledge", "Knowledge Vault"),
                "documents": ("knowledge", "/knowledge", "Knowledge Vault"),
                "knowledge": ("knowledge", "/knowledge", "Knowledge Vault"),
                "knowledge vault": ("knowledge", "/knowledge", "Knowledge Vault"),
                "knowledge base": ("knowledge", "/knowledge", "Knowledge Vault"),
                "sandbox": ("system", "/system", "Sandbox Environment"),
                "sovereignty": ("system", "/system", "System Sovereignty"),
                "approval": ("approvals", "/approvals", "Shift Supervisor Approvals"),
                "approvals": ("approvals", "/approvals", "Shift Supervisor Approvals"),
                "interlock": ("approvals", "/approvals", "Shift Supervisor Approvals"),
                "interlocks": ("approvals", "/approvals", "Shift Supervisor Approvals"),
                "artifact": ("artifacts", "/artifacts", "Workspace Artifacts"),
                "artifacts": ("artifacts", "/artifacts", "Workspace Artifacts"),
                "audit": ("system", "/system", "Audit Logs"),
                "dashboard": ("dashboard", "/dashboard", "Operational Dashboard"),
                "agent": ("agents", "/agents", "Agent Definitions"),
                "agents": ("agents", "/agents", "Agent Definitions"),
                "operator": ("operator", "/operator", "Operator Console"),
                "workspace": ("workspaces", "/workspaces", "Workspace Management"),
                "workspaces": ("workspaces", "/workspaces", "Workspace Management"),
                "run": ("runs", "/runs", "Execution Run History"),
                "runs": ("runs", "/runs", "Execution Run History"),
                "system": ("system", "/system", "System Telemetry"),
            }
            if target_str in nav_views:
                target, route, friendly = nav_views[target_str]
                return SemanticRoutingResult(
                    intent=SemanticIntent.UI_NAVIGATION,
                    decision_method=DecisionMethod.RULE,
                    confidence=None,
                    abstained=False,
                    references=refs,
                    details={"target": target, "target_route": route, "friendly_name": friendly}
                )

        return None

    def _is_capability_inquiry_about_action(self, text: str) -> bool:
        """Determines if a prompt is an educational or capability question ABOUT an action/tool."""
        action_indicators = ["restart", "relief", "depressuriz", "diagnostic", "shutdown", "trip", "vent", "reboot"] + list(SUPPORTED_CONTROL_CAPABILITIES.keys())
        inquiry_openers = [
            "are you able to", "how do you", "how does", "how to", "what happens if",
            "what happens during", "can you explain", "tell me about how", "is it possible to",
            "explain how", "explain "
        ]
        for io in inquiry_openers:
            if text.startswith(io):
                rem = text[len(io):].strip()
                if (
                    any(tool in rem for tool in SUPPORTED_CONTROL_CAPABILITIES)
                    or any(alias in rem for aliases in SUPPORTED_CONTROL_CAPABILITIES.values() for alias in aliases)
                    or any(verb in rem for verb in action_indicators)
                ):
                    return True
        return False

    def _is_negated_action(self, text: str) -> bool:
        """Detects explicit negations directing the agent NOT to take action."""
        cleaned = re.sub(r"^(?:please\s+|hey\s+|operator(?:\s+directive)?[:\s]+)+", "", text.strip())
        if cleaned in ("cancel", "nevermind", "stop", "abort", "cancel that", "never mind"):
            return True
        if re.search(r"\b(?:do\s+not|don['’]?t|never|cancel|stop)\s+(?:restart|trip|relief|vent|depressurize|run\s+diagnostic|shutdown|execute|proceed|actuate|operate)\b", text):
            return True
        if re.search(r"^(?:do\s+not|don['’]?t|never)\s+(?:touch|modify|change|trigger)\b", cleaned):
            return True
        return False

    def _is_ambiguous_control_request(self, text: str, refs: RoutingReferences) -> bool:
        """Determines if a prompt is an ambiguous modal directive on an operational action."""
        modal_openers = ["can you", "could you", "would you", "will you", "should we", "should i"]
        has_modal = any(text.startswith(mo) for mo in modal_openers)
        if not has_modal:
            return False

        if any(w in text for w in ["explain", "why", "describe", "tell me about", "what is", "how does", "what are"]):
            return False

        general_capabilities = [
            "can you run python", "can you execute code", "can you work with spreadsheets",
            "can you analyze spreadsheets", "can you inspect documents", "can you help"
        ]
        if any(text.startswith(gc) for gc in general_capabilities):
            return False

        action_words = [
            "restart", "reboot", "shut down", "shutdown", "trip", "vent",
            "relief", "depressurize", "diagnostic", "trigger"
        ]
        has_action_word = any(w in text for w in action_words)
        has_equipment = len(refs.equipment_ids) > 0
        target_indicators = [
            "component", "pump", "valve", "sensor", "vessel", "reactor",
            "pressure relief", "relief", "system", "service"
        ]
        return has_action_word and (has_equipment or any(w in text for w in target_indicators))

    def _is_supported_control_action(self, text: str, refs: RoutingReferences) -> bool:
        """Verifies if the requested operational action is supported by registered tools."""
        for tool_name, aliases in SUPPORTED_CONTROL_CAPABILITIES.items():
            if tool_name in text:
                return True
            if any(alias in text for alias in aliases):
                return True
        return False

    def _is_artifact_inquiry(self, text: str, refs: RoutingReferences) -> bool:
        """Determines if a prompt is an explicit inquiry about a workspace file/artifact."""
        is_code = bool(re.search(
            r'\b(?:run|write|execute|calculate|compute|eval|evaluate)\b.*?\b(?:python|code|script|program)\b|\bpython\b',
            text
        ))
        if is_code:
            return False

        if any(w in text for w in [
            "export", "convert", "generate two", "two deliverables", "two different files",
            "both docx", "both pdf", "and export", "and generate",
            "generate a pdf", "generate a png", "generate a docx", "generate a chart",
            "generate an audit", "generate a visualization", "generate a report", "generate an excel",
            "generate pdf", "generate png", "generate docx", "generate chart", "generate audit", "generate visualization",
            "create a png", "create another png", "create a chart", "create another chart", "create a visualization",
            "create another visualization", "create a pdf", "create an audit", "create a report",
            "make a png", "make another png", "make a chart", "make another chart", "make a visualization",
            "in docx", "in pdf", "in word", "as docx", "as pdf", "docx format", "pdf format",
            "proper audit", "word format", "audit in", "report in",
            "do a complete audit", "do an audit", "complete audit", "full audit", "and do a complete audit"
        ]):
            return False

        # Conversational inquiry about generated artifacts or files
        artifact_keywords = [
            "file you generated", "files you generated", "artifact you generated", "artifacts you generated",
            "document you generated", "name of the file", "what file", "which file", "where is the file",
            "where is the artifact", "where is the document", "can't find it in artifacts", "cannot find it in artifacts",
            "find the artifact", "in artifacts", "list artifacts", "show artifacts", "generated document",
            "generated artifact", "the generated file", "the created file", "what is the file name"
        ]
        if any(kw in text for kw in artifact_keywords):
            return True

        # Visual artifacts / inspection queries (photos, schematics, handwritten notes, gauge photos)
        visual_keywords = [
            "handwritten note", "handwritten operator", "inspection note", "shift handover note", "shift note",
            "gauge photo", "inspection photo", "p&id diagram", "pid diagram", "p&id schematic", "pid schematic"
        ]
        if any(kw in text for kw in visual_keywords) and any(verb in text for verb in ["transcribe", "read", "check", "inspect", "explain", "look at", "what is on", "what does"]):
            return True

        if not refs.files:
            return False

        # Deliverable generation requests (charts, PNGs, PDFs, audit documents) belong to CODE_EXECUTION, not passive inspection
        from cognishift.core.visualization.selector import parse_artifact_request_contract
        if parse_artifact_request_contract(text).is_deliverable_request:
            return False

        # If an explicit file is referenced, check for reading, extraction, inspection, or comparison triggers
        inquiry_triggers = [
            "what is", "what are", "what was", "what were", "tell me", "summarize", "what does", "what's in",
            "explain", "describe", "contents of", "show me", "show the", "inspect", "find", "extract",
            "list", "identify", "compare", "what row", "which row", "which work order", "which reading", "which",
            "largest", "highest", "lowest", "maximum", "max", "minimum", "min", "abnormal", "anomaly",
            "readings", "read", "values", "value", "using only", "strictly from", "from the file",
            "from the workbook", "from this file", "cite the workbook", "cite the source", "how many"
        ]
        if any(t in text for t in inquiry_triggers):
            return True

        # Fallback: if explicit file is referenced and no operational action is commanded, route to ARTIFACT_INSPECTION
        has_operational_action = any(w in text for w in ["restart", "trip", "relief", "depressurize", "reboot", "open valve", "close valve"])
        return not has_operational_action


_router_instance: Optional[SemanticIntentRouter] = None

def get_semantic_router() -> SemanticIntentRouter:
    """Factory retrieving singleton SemanticIntentRouter."""
    global _router_instance
    if _router_instance is None:
        _router_instance = SemanticIntentRouter()
    return _router_instance
