"""Hardware-Aware Dynamic Model Router for CogniShift."""
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from cognishift.core.model_registry import list_models, ModelDefinition


class TaskClassification(BaseModel):
    """Categorized task profile and inferred capability requirements."""
    task_type: str
    required_capabilities: List[str]
    requires_vision: bool = False
    confidence: float = 0.90


class RoutingCandidateEvaluation(BaseModel):
    """Detailed capability and hardware feasibility evaluation for a candidate model."""
    model_identifier: str
    capability_score: float
    vram_feasible: bool
    vram_required_mb: int
    vram_budget_mb: int
    eligible: bool
    rationale: str


class RoutingDecision(BaseModel):
    """Structured, observable model routing decision."""
    task_type: str
    required_capabilities: List[str]
    selected_model: str
    selected_model_name: str
    selection_reason: str
    candidate_evaluations: Dict[str, RoutingCandidateEvaluation]


def classify_task(prompt: str, has_image: bool = False) -> TaskClassification:
    """
    Analyze incoming user instruction and attached modalities to infer required capabilities.
    """
    text = (prompt or "").lower()

    # 0. Conversational & Capability Meta-Queries (Not an autonomous code execution job)
    if any(q in text for q in ["can you", "what can you", "who are you", "what tools", "what are your", "how do you", "hello", "hi ", "hey"]):
        return TaskClassification(
            task_type="conversational",
            required_capabilities=["reasoning"],
            requires_vision=False,
            confidence=0.95
        )
    
    # 1. Vision & Multimodal Tasks
    if has_image or any(w in text for w in ["photo", "image", "scanned", "diagram", "gauge", "dial", "nameplate", "drawing"]):
        return TaskClassification(
            task_type="vision_inspection",
            required_capabilities=["vision", "ocr"],
            requires_vision=True,
            confidence=0.95
        )

    # 2. Autonomous Coding & Debugging Tasks
    if any(w in text for w in ["python", "script", "program", "code", "csv", "dataframe", "debug", "compile", "execute"]):
        return TaskClassification(
            task_type="coding",
            required_capabilities=["coding", "structured_data"],
            requires_vision=False,
            confidence=0.92
        )

    # 3. Document Analysis & Technical Manual Interpretation
    if any(w in text for w in ["sop", "manual", "inspection report", "oisd", "standard", "procedure", "guideline"]):
        return TaskClassification(
            task_type="document_analysis",
            required_capabilities=["document_analysis", "reasoning"],
            requires_vision=False,
            confidence=0.88
        )

    # 4. Default: General Industrial Reasoning
    return TaskClassification(
        task_type="general_reasoning",
        required_capabilities=["reasoning"],
        requires_vision=False,
        confidence=0.85
    )


def route_model(
    task: TaskClassification,
    available_vram_mb: int = 6000,
    preferred_model: Optional[str] = None
) -> RoutingDecision:
    """
    Hardware-aware model selection algorithm.
    Filters candidate models by VRAM feasibility and scores capability match.
    """
    candidates = list_models(enabled_only=True)
    evaluations: Dict[str, RoutingCandidateEvaluation] = {}
    
    best_candidate: Optional[ModelDefinition] = None
    highest_score = -1.0
    
    for model in candidates:
        # VRAM Feasibility
        is_vram_feasible = model.vram_requirement_mb <= available_vram_mb
        
        # Vision constraint
        has_vision_capability = True
        if task.requires_vision and not model.supports_images:
            has_vision_capability = False
            
        # Capability overlap calculation
        required_set = set(task.required_capabilities)
        model_set = set(model.capabilities)
        overlap = len(required_set.intersection(model_set))
        cap_ratio = overlap / len(required_set) if required_set else 0.5
        
        # Composite score
        composite_score = (
            cap_ratio * 0.70 +
            model.quality_score * 0.20 +
            model.latency_score * 0.10
        )
        
        eligible = is_vram_feasible and has_vision_capability and (overlap > 0 or not task.requires_vision)
        
        rationale = "Eligible candidate"
        if not is_vram_feasible:
            rationale = f"Infeasible (Requires {model.vram_requirement_mb}MB, VRAM budget is {available_vram_mb}MB)"
        elif not has_vision_capability:
            rationale = "Excluded (Task requires vision modality, model is text-only)"
        elif overlap == 0:
            rationale = "Low suitability (0 matching capabilities)"
        else:
            rationale = f"Capability match: {overlap}/{len(required_set)} ({composite_score:.2f})"
            
        evaluations[model.model_identifier] = RoutingCandidateEvaluation(
            model_identifier=model.model_identifier,
            capability_score=round(composite_score, 2),
            vram_feasible=is_vram_feasible,
            vram_required_mb=model.vram_requirement_mb,
            vram_budget_mb=available_vram_mb,
            eligible=eligible,
            rationale=rationale
        )
        
        # Selection logic
        if eligible and composite_score > highest_score:
            highest_score = composite_score
            best_candidate = model

    # Fallback to general model if no candidate matched
    if not best_candidate:
        best_candidate = candidates[0] if candidates else ModelDefinition(
            id="llama3.2:3b",
            name="llama3.2:3b",
            display_name="Fallback Model",
            model_identifier="llama3.2:3b"
        )
        selection_reason = "Fallback model selected (No optimal candidate satisfied all constraints)"
    else:
        selection_reason = f"Highest capability match ({highest_score:.2f}) among hardware-feasible local models"

    return RoutingDecision(
        task_type=task.task_type,
        required_capabilities=task.required_capabilities,
        selected_model=best_candidate.model_identifier,
        selected_model_name=best_candidate.display_name,
        selection_reason=selection_reason,
        candidate_evaluations=evaluations
    )
