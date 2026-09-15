"""
CogniShift End-to-End Engine Dynamic Mutation Test Suite.
Verifies:
1. Dynamic Financial Mutation: Unseen numbers across Revenue, EBITDA, and PAT generate exact mathematical growth calculations without hardcoding.
2. GoalContract Binding: Contract is populated strictly from dynamic calculation facts, never LLM prose.
3. Dynamic SCADA Telemetry Mutation: Dynamic timestamps, sensor tags, and excursion values are recognized by multi-anomaly detector.
4. Prose Validation Authority: Model prose referencing dynamic facts passes; contradictory or hallucinated prose is discarded.
"""
import pytest
import openpyxl
import pandas as pd
from pathlib import Path
from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from cognishift.core.engine import (
    GoalContract,
    populate_goal_contract_from_insights,
    execute_agent_run
)
from cognishift.core.document_insights import (
    extract_spreadsheet_insights,
    detect_dataframe_anomalies,
    validate_scada_anomaly_prose
)


@pytest.fixture(autouse=True)
def set_simulated_mode(monkeypatch):
    monkeypatch.setattr(settings, "operating_mode", "simulated")


def test_dynamic_financial_mutation_and_goal_contract(tmp_path):
    """Verify that mutating financial numbers dynamically propagates to GoalContract with zero hardcoding."""
    wb_path = tmp_path / "mutated_financials.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Financial_Performance"

    # Row 1: Header
    ws.append(["Metric", "FY2025_INR_Cr", "FY2026_INR_Cr"])
    # Dynamic values:
    # Revenue: 240000 -> 300000 (+25.0%)
    # EBITDA: 60000 -> 78000 (+30.0%)
    # PAT: 30000 -> 42000 (+40.0%)
    ws.append(["Gross Revenue", 240000.0, 300000.0])
    ws.append(["Operating Expenses", 180000.0, 222000.0])
    ws.append(["EBITDA", 60000.0, 78000.0])
    ws.append(["Depreciation & Amortization", 15000.0, 16000.0])
    ws.append(["EBIT", 45000.0, 62000.0])
    ws.append(["Finance Costs", 5000.0, 6000.0])
    ws.append(["Profit Before Tax (PBT)", 40000.0, 56000.0])
    ws.append(["Profit After Tax (PAT)", 30000.0, 42000.0])
    wb.save(wb_path)

    # 1. Extract insights dynamically
    insights = extract_spreadsheet_insights(wb_path, query_hint="financial YoY metrics")
    assert insights["is_financial"] is True
    metrics = insights["metrics"]
    growth = insights["growth"]

    # Math verification: zero hardcoding
    assert metrics["revenue"]["previous"] == 240000.0
    assert metrics["revenue"]["latest"] == 300000.0
    assert growth["revenue_yoy_pct"] == 25.0

    assert metrics["ebitda"]["previous"] == 60000.0
    assert metrics["ebitda"]["latest"] == 78000.0
    assert growth["ebitda_yoy_pct"] == 30.0

    assert metrics["pat"]["previous"] == 30000.0
    assert metrics["pat"]["latest"] == 42000.0
    assert growth["pat_yoy_pct"] == 40.0

    # 2. Bind into GoalContract
    contract = GoalContract(required_fields=[
        "revenue_previous", "revenue_current", "revenue_yoy_pct",
        "ebitda_previous", "ebitda_current", "ebitda_yoy_pct",
        "pat_previous", "pat_current", "pat_yoy_pct"
    ])
    populate_goal_contract_from_insights(contract, insights)

    assert contract.is_satisfied() is True
    assert contract.extracted_fields["revenue_current"] == 300000.0
    assert contract.extracted_fields["revenue_yoy_pct"] == 25.0
    assert contract.extracted_fields["ebitda_current"] == 78000.0
    assert contract.extracted_fields["ebitda_yoy_pct"] == 30.0
    assert contract.extracted_fields["pat_current"] == 42000.0
    assert contract.extracted_fields["pat_yoy_pct"] == 40.0


def test_dynamic_scada_anomaly_mutation_and_prose_authority(tmp_path):
    """Verify that mutated SCADA telemetry is accurately detected and validates operator prose."""
    # Build 80 rows of baseline telemetry
    rows = []
    for i in range(1, 81):
        if i == 65:
            # Mutated anomaly row: unseen dynamic values
            rows.append({
                "timestamp": "2026-11-20 14:45:00",
                "tag": "PT-777",
                "description": "Boiler Feed Pump Discharge",
                "discharge_pressure_psi": 612.80,
                "vibration_rms_mm_s": 15.90,
                "sv901_relief_valve_status": "CLOSED",
                "operational_status": "CRITICAL_SPIKE"
            })
        else:
            rows.append({
                "timestamp": f"2026-11-20 {10 + (i // 60):02d}:{i % 60:02d}:00",
                "tag": "PT-777",
                "description": "Boiler Feed Pump Discharge",
                "discharge_pressure_psi": 150.0 + (i % 5) * 0.4,
                "vibration_rms_mm_s": 1.45 + (i % 3) * 0.05,
                "sv901_relief_valve_status": "NORMAL",
                "operational_status": "NORMAL"
            })

    df = pd.DataFrame(rows)
    scada_path = tmp_path / "mutated_scada_log.xlsx"
    df.to_excel(scada_path, index=False)

    # 1. Multi-anomaly ranking & detection
    anomaly = detect_dataframe_anomalies(scada_path)
    assert anomaly["has_anomaly"] is True
    assert anomaly["timestamp"] == "2026-11-20 14:45:00"
    assert anomaly["status_indicator"] == "CRITICAL_SPIKE"
    assert anomaly["valve_status"] == "CLOSED"

    # Spiked columns assertion: 612.8 PSI and 15.9 mm/s
    cols_spiked = {c["column"]: c["value"] for c in anomaly["spiked_columns"]}
    assert "discharge_pressure_psi" in cols_spiked
    assert cols_spiked["discharge_pressure_psi"] == 612.8
    assert "vibration_rms_mm_s" in cols_spiked
    assert cols_spiked["vibration_rms_mm_s"] == 15.9

    # 2. Prose validation: Grounded prose passes
    grounded_prose = (
        "On 2026-11-20 14:45:00, component PT-777 experienced a critical pressure spike "
        "to 612.8 PSI while relief valve SV-901 was closed. Vibration elevated to 15.9 mm/s."
    )
    is_valid, validated_prose = validate_scada_anomaly_prose(
        grounded_prose, anomaly, source_filename="mutated_scada_log.xlsx"
    )
    assert is_valid is True
    assert "612.8" in validated_prose

    # 3. Prose validation: Contradictory valve state fails closed and enforces authoritative card
    contradictory_prose = "The pump operated normally and the relief valve was open at 612.8 PSI."
    is_valid_bad, override_text = validate_scada_anomaly_prose(
        contradictory_prose, anomaly, source_filename="mutated_scada_log.xlsx"
    )
    assert is_valid_bad is False
    assert "Authoritative SCADA Anomaly Detection Report" in override_text
    assert "2026-11-20 14:45:00" in override_text
    assert "612.8" in override_text
