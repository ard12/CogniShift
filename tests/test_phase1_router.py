"""Phase 1 Model Registry & Dynamic Model Router Tests."""
import pytest
from cognishift.core.model_registry import (
    register_model,
    list_models,
    get_model,
    ModelDefinition,
    DEFAULT_MODELS
)
from cognishift.core.model_router import (
    classify_task,
    route_model,
    TaskClassification,
    RoutingDecision
)


def test_task_classification():
    """Verify that task analyzer infers required capabilities correctly."""
    # 1. Coding task
    c1 = classify_task("Write a python script to parse the equipment CSV and compute mean pressure")
    assert c1.task_type == "coding"
    assert "coding" in c1.required_capabilities
    assert not c1.requires_vision

    # 2. Vision inspection task
    c2 = classify_task("Inspect this photo of the analog Bourdon pressure dial", has_image=True)
    assert c2.task_type == "vision_inspection"
    assert "vision" in c2.required_capabilities
    assert c2.requires_vision

    # 3. Document analysis task
    c3 = classify_task("Review the OISD-156 refinery safety standard procedure and extract limits")
    assert c3.task_type == "document_analysis"
    assert "document_analysis" in c3.required_capabilities

    # 4. General reasoning task
    c4 = classify_task("Explain why secondary containment is necessary for hydrocracker vessels")
    assert c4.task_type == "general_reasoning"
    assert "reasoning" in c4.required_capabilities


def test_model_routing_coding():
    """Verify that coding task routes to coding specialist within VRAM budget."""
    task = classify_task("Write a python data processing script")
    decision = route_model(task, available_vram_mb=6000)

    assert decision.selected_model == "qwen2.5-coder:7b"
    assert "coding" in decision.required_capabilities
    assert decision.candidate_evaluations["qwen2.5-coder:7b"].vram_feasible is True
    assert decision.candidate_evaluations["qwen2.5-coder:7b"].eligible is True


def test_model_routing_vram_constraint():
    """Verify that models exceeding VRAM budget are marked infeasible."""
    task = classify_task("Analyze complex refinery hydrocracker failure modes")
    decision = route_model(task, available_vram_mb=8000)

    # deepseek-r1:14b requires 14000MB, budget is 8000MB
    deepseek_eval = decision.candidate_evaluations["deepseek-r1:14b"]
    assert deepseek_eval.vram_feasible is False
    assert deepseek_eval.eligible is False
    assert "Infeasible" in deepseek_eval.rationale
    # Should select feasible model (llama3.2:3b)
    assert decision.selected_model == "llama3.2:3b"


def test_model_routing_vision():
    """Verify that vision task routes to image-capable model."""
    task = classify_task("Read the needle angle on this pressure gauge photo", has_image=True)
    decision = route_model(task, available_vram_mb=6000)

    assert decision.selected_model == "moondream"
    assert decision.candidate_evaluations["moondream"].eligible is True
    # Text-only models should be excluded from vision tasks
    assert decision.candidate_evaluations["llama3.2:3b"].eligible is False
    assert "Excluded" in decision.candidate_evaluations["llama3.2:3b"].rationale


def test_model_registry_extensibility():
    """Verify that adding a new model via configuration requires zero engine code changes."""
    new_model = ModelDefinition(
        id="custom-sensor-agent:8b",
        name="custom-sensor-agent:8b",
        display_name="Custom Industrial Sensor Specialist 8B",
        model_identifier="custom-sensor-agent:8b",
        capabilities=["sensor_diagnostics", "reasoning"],
        context_window=16384,
        vram_requirement_mb=4500,
        quality_score=0.96,
        latency_score=0.90,
        priority=130
    )
    register_model(new_model)

    retrieved = get_model("custom-sensor-agent:8b")
    assert retrieved is not None
    assert retrieved.display_name == "Custom Industrial Sensor Specialist 8B"
    assert "custom-sensor-agent:8b" in [m.model_identifier for m in list_models()]

    # Verify router immediately considers this new model in evaluations
    task = TaskClassification(
        task_type="diagnostics",
        required_capabilities=["sensor_diagnostics"],
        requires_vision=False
    )
    decision = route_model(task, available_vram_mb=6000)
    assert "custom-sensor-agent:8b" in decision.candidate_evaluations
    assert decision.selected_model == "custom-sensor-agent:8b"
