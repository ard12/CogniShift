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
    "restart_component": ["restart", "reboot", "cycle power", "component restart"],
    "emergency_pressure_relief": ["emergency pressure relief", "pressure relief", "depressurize", "emergency vent", "emergency trip"],
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
        "how do you check sensor telemetry"
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
        "what does the remote work policy say"
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
        "execute data processing script in the sandbox"
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

        # 4.5. Deterministic Rule: Explicit Imperative Code Execution Request
        # e.g. "run a simple python script of your choice that can generate us a report on the latest ingested document"
        is_question = any(text_lower.startswith(qo) for qo in [
            "can you", "could you", "would you", "how do you", "how can", "is it possible",
            "what can", "what is", "explain", "tell me"
        ])
        is_imperative_code = bool(re.search(
            r'^\s*(?:please\s+)?(?:run|execute|write\s+and\s+run)\b.*?\b(?:python|code|script|program)\b',
            text_lower
        ))
        if is_imperative_code and not is_question:
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
            "is there a", "are there any", "do we have"
        ]
        if any(text_lower.startswith(qo) for qo in question_openers):
            if SemanticIntent.CONTROL_ACTION in scores:
                scores[SemanticIntent.CONTROL_ACTION] = 0.0

        sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_intent, top_score = sorted_intents[0]
        runner_up_intent, runner_up_score = sorted_intents[1]
        margin = top_score - runner_up_score

        # 6. Unsupported Action Guard for CONTROL_ACTION
        if top_intent == SemanticIntent.CONTROL_ACTION:
            is_supported = self._is_supported_control_action(text_lower, refs)
            if not is_supported:
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
            if top_score < self.control_confidence_threshold or margin < self.control_margin_threshold:
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
        clean_text = text.strip().rstrip('.?!,;').strip()
        slash_commands = {
            "/documents": "documents",
            "/sandbox": "sandbox",
            "/sovereignty": "sovereignty",
            "/approvals": "approvals",
            "/artifacts": "artifacts",
            "/audit": "audit",
            "/dashboard": "dashboard",
            "/agents": "agents",
            "/help": "help",
            "/status": "status",
            "/policy": "policy"
        }
        if clean_text in slash_commands:
            return SemanticRoutingResult(
                intent=SemanticIntent.UI_NAVIGATION,
                decision_method=DecisionMethod.RULE,
                confidence=None,
                abstained=False,
                references=refs,
                details={"target": slash_commands[clean_text]}
            )

        exact_nav_phrases = {
            "open documents", "show documents", "list documents",
            "open sandbox", "show sandbox",
            "open sovereignty", "show sovereignty", "network monitor",
            "open approvals", "show approvals", "show pending approvals",
            "take me to approvals", "take me to approvals view", "go to approvals",
            "open artifacts", "show artifacts", "list artifacts",
            "open audit", "show audit", "show audit logs", "audit logs",
            "open dashboard", "show dashboard", "go to dashboard"
        }
        if clean_text in exact_nav_phrases:
            return SemanticRoutingResult(
                intent=SemanticIntent.UI_NAVIGATION,
                decision_method=DecisionMethod.RULE,
                confidence=None,
                abstained=False,
                references=refs,
                details={"phrase": clean_text}
            )

        # Regex matching for navigation commands (e.g. "take me to ... view", "go to ... page")
        nav_match = re.match(r'^(?:take me to|go to|navigate to|switch to|open|show)\s+(?:the\s+)?([a-z0-9_\-\s]+?)(?:\s+view|\s+page|\s+tab)?$', clean_text)
        if nav_match:
            target_str = nav_match.group(1).strip()
            nav_views = {
                "document": "documents", "documents": "documents",
                "sandbox": "sandbox", "sovereignty": "sovereignty",
                "approval": "approvals", "approvals": "approvals",
                "artifact": "artifacts", "artifacts": "artifacts",
                "audit": "audit", "dashboard": "dashboard",
                "agent": "agents", "agents": "agents",
                "workspace": "workspaces", "workspaces": "workspaces"
            }
            if target_str in nav_views:
                return SemanticRoutingResult(
                    intent=SemanticIntent.UI_NAVIGATION,
                    decision_method=DecisionMethod.RULE,
                    confidence=None,
                    abstained=False,
                    references=refs,
                    details={"target": nav_views[target_str]}
                )

        return None

    def _is_capability_inquiry_about_action(self, text: str) -> bool:
        """Determines if a prompt is an educational or capability question ABOUT an action."""
        inquiry_openers = [
            "are you able to", "how do you", "how does", "how to", "what happens if",
            "what happens during", "can you explain", "tell me about how", "is it possible to",
            "explain how"
        ]
        if any(text.startswith(io) for io in inquiry_openers):
            return True
        if text.startswith("explain "):
            rem = text[len("explain "):].strip()
            if any(tool in rem for tool in SUPPORTED_CONTROL_CAPABILITIES):
                return True
            if any(verb in rem for verb in ["restart", "relief", "depressuriz", "diagnostic", "shutdown", "trip"]):
                return True
        return False

    def _is_negated_action(self, text: str) -> bool:
        """Detects explicit negations directing the agent NOT to take action."""
        negation_openers = ["do not ", "don't ", "dont ", "never ", "nevermind", "cancel "]
        return any(text.startswith(no) for no in negation_openers)

    def _is_ambiguous_control_request(self, text: str, refs: RoutingReferences) -> bool:
        """Determines if a prompt is an ambiguous modal directive on an operational action."""
        modal_openers = ["can you", "could you", "would you", "will you", "should we", "should i"]
        has_modal = any(text.startswith(mo) for mo in modal_openers)
        if not has_modal:
            return False

        general_capabilities = [
            "can you run python", "can you execute code", "can you work with spreadsheets",
            "can you analyze spreadsheets", "can you inspect documents", "can you help"
        ]
        if any(text.startswith(gc) for gc in general_capabilities):
            return False

        action_words = [
            "restart", "reboot", "shut down", "shutdown", "trip", "vent",
            "relief", "depressurize", "diagnostic"
        ]
        has_action_word = any(w in text for w in action_words)
        has_equipment = len(refs.equipment_ids) > 0
        return has_action_word or has_equipment

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
        if not refs.files:
            return False

        is_code = bool(re.search(
            r'\b(?:run|write|execute|calculate|compute|eval|evaluate)\b.*?\b(?:python|code|script|program)\b|\bpython\b',
            text
        ))
        if is_code:
            return False

        inquiry_triggers = [
            "what is", "tell me about", "summarize", "what does", "what's in",
            "explain", "describe", "contents of", "show me the readings", "inspect",
            "what information is in", "show me the summary", "what is inside", "about",
            "report on", "generate a report", "create a report", "review"
        ]
        return any(t in text for t in inquiry_triggers)


_router_instance: Optional[SemanticIntentRouter] = None

def get_semantic_router() -> SemanticIntentRouter:
    """Factory retrieving singleton SemanticIntentRouter."""
    global _router_instance
    if _router_instance is None:
        _router_instance = SemanticIntentRouter()
    return _router_instance
