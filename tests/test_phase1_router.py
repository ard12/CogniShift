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

    # 5. Data artifact inquiry task (must NOT trigger coding)
    c5 = classify_task("can you tell me about processed_equipment_readings.csv")
    assert c5.task_type == "document_analysis"
    assert "document_analysis" in c5.required_capabilities
    assert not c5.requires_vision


def test_model_routing_coding():
    """Verify that coding task routes to coding specialist within VRAM budget."""
    task = classify_task("Write a python data processing script")
    decision = route_model(task, available_vram_mb=6000)

    assert decision.selected_model == "qwen2.5-coder:7b"
    assert "coding" in decision.required_capabilities
    assert decision.candidate_evaluations["qwen2.5-coder:7b"].vram_feasible is True
    assert decision.candidate_evaluations["qwen2.5-coder:7b"].eligible is True


def test_model_routing_local_installation_filtering():
    """Verify that router excludes uninstalled models and routes to available installed general SLM."""
    task = classify_task("Write a python data processing script")
    # Simulate host where qwen2.5-coder:7b is NOT installed
    installed = ["qwen2.5:7b", "llama3.2:3b", "moondream:latest"]
    decision = route_model(task, available_vram_mb=6000, installed_models=installed)

    # qwen2.5-coder:7b must be marked ineligible
    assert decision.candidate_evaluations["qwen2.5-coder:7b"].eligible is False
    assert "Excluded" in decision.candidate_evaluations["qwen2.5-coder:7b"].rationale
    # Must cleanly select installed qwen2.5:7b without throwing 404
    assert decision.selected_model == "qwen2.5:7b"
    assert decision.candidate_evaluations["qwen2.5:7b"].eligible is True


def test_model_routing_heavy_reasoning():
    """Verify that root cause analysis and heavy reasoning route to DeepSeek R1 within VRAM budget."""
    task = classify_task("Perform root cause analysis on the cooling pump tripping incident")
    assert task.task_type == "heavy_reasoning"
    assert "heavy_reasoning" in task.required_capabilities

    # 1. When DeepSeek is available in catalog within 6GB budget
    decision = route_model(task, available_vram_mb=6000)
    assert decision.selected_model == "deepseek-r1:7b"
    assert decision.candidate_evaluations["deepseek-r1:7b"].eligible is True

    # 2. When DeepSeek is not installed on the local machine
    installed = ["qwen2.5:7b", "llama3.2:3b", "moondream:latest"]
    decision_fallback = route_model(task, available_vram_mb=6000, installed_models=installed)
    assert decision_fallback.selected_model == "qwen2.5:7b"
    assert decision_fallback.candidate_evaluations["deepseek-r1:7b"].eligible is False


def test_model_routing_vram_constraint():
    """Verify that models exceeding VRAM budget are marked infeasible."""
    task = classify_task("Analyze complex refinery hydrocracker failure modes")
    decision = route_model(task, available_vram_mb=8000)

    # deepseek-r1:14b requires 14000MB, budget is 8000MB
    deepseek_eval = decision.candidate_evaluations["deepseek-r1:14b"]
    assert deepseek_eval.vram_feasible is False
    assert deepseek_eval.eligible is False
    assert "Infeasible" in deepseek_eval.rationale
    # Should select feasible model (qwen2.5:7b or llama3.2:3b)
    assert decision.selected_model in ["qwen2.5:7b", "llama3.2:3b"]


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


def test_model_routing_exact_tag_matching():
    """Edge Case A: Installing deepseek-r1:14b must NOT make deepseek-r1:7b eligible."""
    task = classify_task("Perform root cause analysis on the cooling pump tripping incident")
    # Host has ONLY the 14b variant installed
    installed = ["deepseek-r1:14b", "qwen2.5:7b", "llama3.2:3b"]
    decision = route_model(task, available_vram_mb=6000, installed_models=installed)

    # 7b variant must be marked uninstalled
    eval_7b = decision.candidate_evaluations["deepseek-r1:7b"]
    assert eval_7b.eligible is False
    assert "Excluded (Model not installed on local sovereign runtime)" in eval_7b.rationale

    # 14b variant is infeasible within 6000MB budget (requires 14000MB)
    eval_14b = decision.candidate_evaluations["deepseek-r1:14b"]
    assert eval_14b.eligible is False
    assert "Infeasible" in eval_14b.rationale

    # Router must fall back to feasible installed model (qwen2.5:7b)
    assert decision.selected_model == "qwen2.5:7b"


def test_model_routing_zero_overlap_ineligibility():
    """Edge Case B: Models with zero capability overlap must be marked eligible=False."""
    # Task with a specialized capability not possessed by general SLMs
    task = TaskClassification(
        task_type="isolated_test_task",
        required_capabilities=["sensor_diagnostics"],
        requires_vision=False
    )
    decision = route_model(task, available_vram_mb=6000, installed_models=["qwen2.5:7b", "llama3.2:3b"])

    # qwen2.5:7b has no "sensor_diagnostics" in default registry
    qwen_eval = decision.candidate_evaluations["qwen2.5:7b"]
    # If custom-sensor-agent:8b is in registry, it matches, otherwise zero-overlap models are ineligible
    if "sensor_diagnostics" not in get_model("qwen2.5:7b").capabilities:
        assert qwen_eval.eligible is False
        assert "Zero overlap" in qwen_eval.rationale


def test_model_routing_inventory_lookup_failure():
    """Edge Case C: If local inventory lookup yields empty list or fails, router falls back safely."""
    task = classify_task("Analyze log data")
    decision = route_model(task, available_vram_mb=6000, installed_models=[])

    # With no models installed, all candidates are marked ineligible
    for cand_eval in decision.candidate_evaluations.values():
        assert cand_eval.eligible is False

    # Still selects a safe fallback definition without crashing
    assert decision.selected_model is not None
    assert "Fallback" in decision.selection_reason

