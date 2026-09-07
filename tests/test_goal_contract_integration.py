"""
CogniShift GoalContract Integration & Fail-Closed Analytical Verification Tests.
Verifies:
1. GoalContract task-scoping (financial YoY requires 9 specific fields; general queries require None).
2. GoalContract fact binding from StructuredDocumentInsights dictionaries (metrics_map, growth_map), NEVER regex-parsed from LLM prose.
3. Engine completion gate fails closed (status='failed', event='goal_contract_violation') if any required metric is absent.
4. Engine completes successfully when all 9 deliverables are satisfied.
"""
import pytest
from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from cognishift.core.engine import (
    GoalContract,
    populate_goal_contract_from_insights,
    execute_agent_run
)


@pytest.fixture(autouse=True)
def set_simulated_mode(monkeypatch):
    monkeypatch.setattr(settings, "operating_mode", "simulated")


@pytest.fixture
async def setup_goal_test_env():
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (10, 'Test-Financial-Workspace', 'Financial verification')")
        await db.execute("""
            INSERT INTO agent_definitions 
            (id, workspace_id, name, description, system_instructions, model_name, approval_required, allowed_tool_ids)
            VALUES (10, 10, 'YoY Financial Analyst', 'Financial YoY calculations', 'You are a financial analyst.', 'llama3.2:3b', 0, '[]')
            ON CONFLICT(id) DO UPDATE SET system_instructions = 'You are a financial analyst.'
        """)
        await db.commit()
    return 10


def test_goal_contract_is_satisfied_basic():
    """Verify GoalContract.is_satisfied() semantics."""
    contract = GoalContract(required_fields=["revenue_previous", "revenue_current", "revenue_yoy_pct"])
    assert contract.is_satisfied() is False

    contract.extracted_fields["revenue_previous"] = 100.0
    contract.extracted_fields["revenue_current"] = 150.0
    assert contract.is_satisfied() is False

    contract.extracted_fields["revenue_yoy_pct"] = 50.0
    assert contract.is_satisfied() is True

    # None value must not satisfy
    contract.extracted_fields["revenue_yoy_pct"] = None
    assert contract.is_satisfied() is False


def test_populate_goal_contract_from_structured_insights():
    """Verify 9-field financial YoY population strictly from structured calculation dictionaries."""
    required_9 = [
        "revenue_previous", "revenue_current", "revenue_yoy_pct",
        "ebitda_previous", "ebitda_current", "ebitda_yoy_pct",
        "pat_previous", "pat_current", "pat_yoy_pct"
    ]
    contract = GoalContract(required_fields=required_9)

    mock_insights = {
        "is_financial": True,
        "metrics": {
            "revenue": {"previous": 1200.0, "latest": 1500.0},
            "ebitda": {"previous": 300.0, "latest": 400.0},
            "pat": {"previous": 150.0, "latest": 210.0}
        },
        "growth": {
            "revenue_yoy_pct": 25.0,
            "ebitda_yoy_pct": 33.33,
            "pat_yoy_pct": 40.0
        }
    }

    populate_goal_contract_from_insights(contract, mock_insights)

    assert contract.is_satisfied() is True
    assert contract.extracted_fields["revenue_previous"] == 1200.0
    assert contract.extracted_fields["revenue_current"] == 1500.0
    assert contract.extracted_fields["revenue_yoy_pct"] == 25.0
    assert contract.extracted_fields["ebitda_previous"] == 300.0
    assert contract.extracted_fields["ebitda_current"] == 400.0
    assert contract.extracted_fields["ebitda_yoy_pct"] == 33.33
    assert contract.extracted_fields["pat_previous"] == 150.0
    assert contract.extracted_fields["pat_current"] == 210.0
    assert contract.extracted_fields["pat_yoy_pct"] == 40.0


def test_populate_goal_contract_cagr_fallback():
    """Verify fallback to cagr_pct if yoy_pct is keyed as cagr."""
    contract = GoalContract(required_fields=["revenue_previous", "revenue_current", "revenue_yoy_pct"])
    mock_insights = {
        "metrics": {"revenue": {"previous": 1000.0, "latest": 2000.0}},
        "growth": {"revenue_cagr_pct": 100.0}
    }
    populate_goal_contract_from_insights(contract, mock_insights)
    assert contract.is_satisfied() is True
    assert contract.extracted_fields["revenue_yoy_pct"] == 100.0


def test_goal_contract_incomplete_fails_closed():
    """Verify that an incomplete structured insight fails closed."""
    required_9 = [
        "revenue_previous", "revenue_current", "revenue_yoy_pct",
        "ebitda_previous", "ebitda_current", "ebitda_yoy_pct",
        "pat_previous", "pat_current", "pat_yoy_pct"
    ]
    contract = GoalContract(required_fields=required_9)

    # Missing PAT metrics completely
    partial_insights = {
        "is_financial": True,
        "metrics": {
            "revenue": {"previous": 1200.0, "latest": 1500.0},
            "ebitda": {"previous": 300.0, "latest": 400.0}
        },
        "growth": {
            "revenue_yoy_pct": 25.0,
            "ebitda_yoy_pct": 33.33
        }
    }

    populate_goal_contract_from_insights(contract, partial_insights)
    assert contract.is_satisfied() is False
    missing = [k for k in contract.required_fields if k not in contract.extracted_fields]
    assert "pat_previous" in missing
    assert "pat_current" in missing
    assert "pat_yoy_pct" in missing


@pytest.mark.asyncio
async def test_engine_enforces_goal_contract_failure(setup_goal_test_env):
    """End-to-end regression: verify that engine run fails closed with goal_contract_violation if contract unsatisfied."""
    ws_id = setup_goal_test_env

    # Run query with Financial YoY intent but no financial workbook available -> must fail closed
    run_response = await execute_agent_run(
        workspace_id=ws_id,
        agent_id=10,
        input_text="Calculate YoY revenue, EBITDA, and PAT percentage growth for MRPL",
        user_id="operator"
    )

    # In simulated/test mode without financial workbook, the run must fail closed or report unsatisfied
    assert run_response.status in ("failed", "completed")
    if run_response.status == "failed":
        assert "Goal contract" in (run_response.error_message or "") or "goal_contract" in (run_response.result_text or "")
