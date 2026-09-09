"""Comprehensive Test Suite for Native FastEmbed Semantic Intent Router."""

import pytest
from cognishift.core.semantic_router import (
    get_semantic_router,
    SemanticIntent,
    DecisionMethod,
    SemanticRoutingResult,
    SemanticIntentRouter
)


@pytest.fixture(scope="module")
def router():
    return get_semantic_router()


# -----------------------------------------------------------------------------
# 1. CONVERSATIONAL & CAPABILITY INQUIRIES
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("query", [
    "hello",
    "hi there",
    "who are you",
    "what is cognishift",
    "tell me about yourself",
    "can you run python",
    "can you run a python program",
    "can you run python scripts",
    "do you support python execution",
    "what programming languages can you run",
    "what can you do",
    "what are your capabilities",
    "how does your sandbox work",
    "explain your architecture",
    "what tools do you have",
    "explain restart_component",
    "how does the diagnostic tool work",
    "how do you check pressure"
])
def test_conversational_and_capability_routing(router, query):
    res = router.route(query)
    assert res.intent == SemanticIntent.CONVERSATION, f"Failed on '{query}': got {res.intent}"
    if res.confidence is not None:
        assert res.confidence >= 0.70
    assert not res.abstained


# -----------------------------------------------------------------------------
# 2. ZERO FALSE POSITIVE ACTION GUARANTEE (Questions vs Commands)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("question_query,expected_intent", [
    ("Can you restart P-101A?", SemanticIntent.COMPLEX_AGENT),
    ("Could you restart the pump?", SemanticIntent.COMPLEX_AGENT),
    ("Is it possible to restart P-101A?", SemanticIntent.CONVERSATION),
    ("How do you restart a component?", SemanticIntent.CONVERSATION),
    ("How does emergency pressure relief work?", SemanticIntent.CONVERSATION),
    ("Can you trigger pressure relief?", SemanticIntent.COMPLEX_AGENT),
    ("What happens if we restart P-101A?", SemanticIntent.CONVERSATION),
    ("Explain the restart_component procedure", SemanticIntent.CONVERSATION),
    ("Are you able to restart equipment?", SemanticIntent.CONVERSATION),
    ("Should we restart P-101A?", SemanticIntent.COMPLEX_AGENT)
])
def test_zero_false_positive_for_action_questions(router, question_query, expected_intent):
    """Questions about actions must NEVER trigger CONTROL_ACTION."""
    res = router.route(question_query)
    assert res.intent != SemanticIntent.CONTROL_ACTION, (
        f"CRITICAL SAFETY VIOLATION: Question '{question_query}' routed to CONTROL_ACTION!"
    )
    assert res.intent == expected_intent


# -----------------------------------------------------------------------------
# 3. KNOWLEDGE / SOP INQUIRIES
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("knowledge_query", [
    "what does our sop say about vibration",
    "what does our centrifugal pump sop say",
    "what is the bearing temperature limit",
    "what is the normal discharge pressure range",
    "what are the safe suction pressure thresholds",
    "which procedure applies to P-101A",
    "what is the maximum allowable working pressure according to API 610",
    "what does the standard operating procedure state for seal flush",
    "what are the refinery safety guidelines for hydrocracker vessels",
    "what does the turbine manual say about steam pressure",
    "what is the allowable operating envelope in OISD-156",
    "which page of the manual contains the temperature limits"
])
def test_knowledge_query_routing(router, knowledge_query):
    res = router.route(knowledge_query)
    assert res.intent == SemanticIntent.KNOWLEDGE_QUERY, f"Failed on '{knowledge_query}': got {res.intent}"
    assert res.confidence >= 0.70


# -----------------------------------------------------------------------------
# 4. WORKSPACE ARTIFACT INSPECTION
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("artifact_query", [
    "what is maintenance_plan_P-101A.yaml about?",
    "what is maintenance_plan_P-101A.yaml even about?",
    "explain maintenance_plan_P-101A.yaml",
    "summarize processed_equipment_readings.csv",
    "what does processed_equipment_readings.csv contain?",
    "explain the contents of final_report.csv",
    "what is inside valid_data.csv",
    "describe the generated report file",
    "inspect the artifact file in workspace"
])
def test_artifact_inspection_routing(router, artifact_query):
    res = router.route(artifact_query)
    assert res.intent == SemanticIntent.ARTIFACT_INSPECTION, f"Failed on '{artifact_query}': got {res.intent}"
    if res.confidence is not None:
        assert res.confidence >= 0.75


# -----------------------------------------------------------------------------
# 5. PYTHON / SANDBOX CODE EXECUTION
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("code_query", [
    "run python on equipment_readings.csv",
    "run python to analyze readings.csv",
    "run python to find anomalous rows in equipment_readings.csv",
    "write and execute python to find anomalies",
    "calculate anomalies using python",
    "write and execute a script for this csv",
    "execute python code in the sandbox to compute mean pressure",
    "run a python script to parse the equipment logs",
    "compute statistical 3-sigma values using python in sandbox"
])
def test_code_execution_routing(router, code_query):
    res = router.route(code_query)
    assert res.intent == SemanticIntent.CODE_EXECUTION, f"Failed on '{code_query}': got {res.intent}"
    assert res.confidence >= 0.75


# -----------------------------------------------------------------------------
# 6. OPERATIONAL CONTROL ACTION COMMANDS
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("action_command", [
    "restart P-101A now",
    "restart P-101A",
    "please restart P-101A immediately",
    "execute emergency pressure relief",
    "trigger emergency pressure relief on unit 1",
    "run the diagnostic tool on PT-101",
    "run equipment diagnostic on P-101A",
    "execute component restart on booster pump",
    "trigger emergency trip on P-101A"
])
def test_control_action_routing(router, action_command):
    res = router.route(action_command)
    assert res.intent == SemanticIntent.CONTROL_ACTION, f"Failed on '{action_command}': got {res.intent}"
    assert res.confidence >= 0.70
    assert not res.abstained


# -----------------------------------------------------------------------------
# 7. UI NAVIGATION COMMANDS
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("nav_query,expected_target", [
    ("/documents", "documents"),
    ("/sandbox", "sandbox"),
    ("/sovereignty", "sovereignty"),
    ("/approvals", "approvals"),
    ("/artifacts", "artifacts"),
    ("/audit", "audit"),
    ("/dashboard", "dashboard"),
    ("open documents", None),
    ("open sandbox", None),
    ("open sovereignty", None),
    ("show audit logs", None)
])
def test_ui_navigation_routing(router, nav_query, expected_target):
    res = router.route(nav_query)
    assert res.intent == SemanticIntent.UI_NAVIGATION
    assert res.decision_method == DecisionMethod.RULE
    assert res.confidence is None
    if expected_target:
        assert res.details.get("target") == expected_target


# -----------------------------------------------------------------------------
# 8. SAFE ABSTENTION ON AMBIGUOUS MULTI-INTENT QUERIES
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("ambiguous_query", [
    "Check P-101A and tell me what to do.",
    "Look into the system and advise on our next steps.",
    "What should we do with unit 2?"
])
def test_safe_abstention_to_complex_agent(router, ambiguous_query):
    """Queries that blur multiple intents or lack margin must abstain to COMPLEX_AGENT."""
    res = router.route(ambiguous_query)
    assert res.intent == SemanticIntent.COMPLEX_AGENT or res.abstained is True
    if res.confidence is not None:
        assert res.confidence < 0.95


# -----------------------------------------------------------------------------
# 9. SERIALIZATION AND OBSERVABILITY
# -----------------------------------------------------------------------------
def test_routing_result_serialization(router):
    res = router.route("can you run a python program?")
    d = res.to_dict()
    assert d["intent"] == "CONVERSATION"
    assert isinstance(d["confidence"], float)
    assert d["decision_method"] == "SEMANTIC"
    assert "details" in d
    assert "references" in d
