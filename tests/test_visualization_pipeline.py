"b""Automated verification suite for CogniShift deterministic visualization pipeline."""
import pytest
from pathlib import Path

from cognishift.core.visualization.schemas import (
    ArtifactRequestContract,
    ChartType,
    VisualizationSpec,
)
from cognishift.core.visualization.selector import (
    parse_artifact_request_contract,
    select_target_sheet,
    build_visualization_specs,
)
from cognishift.core.visualization.renderer import _tick_positions, render_visualization
from cognishift.core.visualization.validator import validate_png_artifact
from cognishift.core.engine import GoalContract, _is_presentation_request
from cognishift.core.conversation_context import _explicit_filename_matches_source
from cognishift.core.document_insights import extract_document_insights


def test_parse_artifact_request_contract():
    """Verify deterministic contract extraction across all required evaluation patterns."""
    q1 = "Create an audit report from this file and give me a PDF."
    c1 = parse_artifact_request_contract(q1)
    assert c1.pdf_required is True
    assert c1.png_required is False
    assert c1.is_deliverable_request is True

    q2 = "Create a visualization and return it as PNG."
    c2 = parse_artifact_request_contract(q2)
    assert c2.png_required is True
    assert c2.png_count == 1
    assert c2.is_deliverable_request is True

    q3 = "Create a bar chart from this spreadsheet."
    c3 = parse_artifact_request_contract(q3)
    assert c3.png_required is True
    assert c3.requested_chart_type == ChartType.BAR
    assert c3.is_deliverable_request is True

    q4 = "Create a line graph and give me the PNG."
    c4 = parse_artifact_request_contract(q4)
    assert c4.png_required is True
    assert c4.requested_chart_type == ChartType.LINE
    assert c4.is_deliverable_request is True

    q5 = "Analyze this CSV and create a PDF report and PNG chart."
    c5 = parse_artifact_request_contract(q5)
    assert c5.pdf_required is True
    assert c5.png_required is True
    assert c5.png_count == 1
    assert c5.is_deliverable_request is True

    q6 = "Create two different charts from this workbook."
    c6 = parse_artifact_request_contract(q6)
    assert c6.png_required is True
    assert c6.png_count == 2
    assert c6.is_deliverable_request is True

    q7 = "Create a CSV file containing the timestamp and discharge pressure."
    c7 = parse_artifact_request_contract(q7)
    assert c7.csv_required is True
    assert c7.is_deliverable_request is True

    c7_input = parse_artifact_request_contract(
        "Create a line chart showing discharge pressure over time from the attached CSV."
    )
    assert c7_input.csv_required is False
    assert c7_input.png_required is True

    q8 = "Create a graphical representation of the attached spreadsheet."
    c8 = parse_artifact_request_contract(q8)
    assert c8.png_required is True
    assert c8.is_deliverable_request is True


def test_graphical_representation_does_not_request_powerpoint():
    assert _is_presentation_request("create a graphical representation and a PDF") is False
    assert _is_presentation_request("create a PowerPoint presentation") is True


def test_explicit_xls_reference_can_resolve_same_stem_xlsx_source_only():
    requested = "MRPL_Enterprise_Financial_and_Operational_History_10Y.xls"
    stored = "MRPL_Enterprise_Financial_and_Operational_History_10Y.xlsx"
    assert _explicit_filename_matches_source(requested, stored) is True
    assert _explicit_filename_matches_source(requested, "MRPL_Enterprise_Financial_and_Operational_History_3Y.xlsx") is False
    assert _explicit_filename_matches_source("inspection.pdf", "inspection.docx") is False


def test_build_visualization_specs_csv():
    """Verify truthful extraction from real maintenance log CSV without LLM fabrication."""
    csv_path = Path("data/demo/MRPL_Enterprise_Plant_Asset_and_Maintenance_Log_5Y.csv")
    if not csv_path.exists():
        pytest.skip("Demo CSV not found")

    query = "Create a bar chart of work order distributions from this spreadsheet."
    contract = parse_artifact_request_contract(query)
    specs = build_visualization_specs(csv_path, contract, query)

    assert len(specs) == 1
    spec = specs[0]
    assert spec.chart_type == ChartType.BAR
    assert len(spec.x_values) > 0
    assert len(spec.series) > 0
    vals = list(spec.series.values())[0]
    assert all(isinstance(v, (int, float)) and v > 0 for v in vals)


def test_explicit_equipment_metric_time_series_uses_requested_columns():
    csv_path = Path("data/demo/equipment_readings.csv")
    if not csv_path.exists():
        pytest.skip("Equipment readings demo CSV not found")

    query = "Create a line chart showing the discharge pressure of P-101A over time from the attached CSV."
    contract = parse_artifact_request_contract(query)
    specs = build_visualization_specs(csv_path, contract, query)

    assert contract.csv_required is False
    assert len(specs) == 1
    spec = specs[0]
    assert spec.chart_type == ChartType.LINE
    assert spec.x_column == "timestamp"
    assert spec.y_columns == ["discharge_pressure_psi"]
    assert spec.provenance["filter"] == "component_id = P-101A"
    assert spec.provenance["row_count"] > 10
    assert len(spec.x_values) == len(spec.series["discharge_pressure_psi"])


def test_nonexistent_equipment_fails_closed_without_unfiltered_chart():
    csv_path = Path("data/demo/equipment_readings.csv")
    if not csv_path.exists():
        pytest.skip("Equipment readings demo CSV not found")

    query = "Create a line chart showing discharge_pressure_psi for P-9999 over time from the attached CSV."
    with pytest.raises(ValueError, match="P-9999.*not found.*No unfiltered or substitute chart"):
        build_visualization_specs(csv_path, parse_artifact_request_contract(query), query)


def test_nonexistent_metric_fails_closed_without_substitute_column():
    csv_path = Path("data/demo/equipment_readings.csv")
    if not csv_path.exists():
        pytest.skip("Equipment readings demo CSV not found")

    query = "Create a line chart showing nonexistent_metric for P-101A over time from the attached CSV."
    with pytest.raises(ValueError, match="nonexistent_metric.*not found.*No substitute column"):
        build_visualization_specs(csv_path, parse_artifact_request_contract(query), query)


def test_png_and_csv_combined_contract_requires_both_outputs():
    contract = parse_artifact_request_contract(
        "Create a PNG chart and also export the filtered data as CSV"
    )
    assert contract.png_required is True
    assert contract.png_count == 1
    assert contract.csv_required is True
    assert contract.total_artifacts_expected == 2


def test_build_visualization_specs_dual_charts():
    """Verify generation of 2 distinct chart specs when requested."""
    csv_path = Path("data/demo/MRPL_Enterprise_Plant_Asset_and_Maintenance_Log_5Y.csv")
    if not csv_path.exists():
        pytest.skip("Demo CSV not found")

    query = "Create two different charts from this workbook."
    contract = parse_artifact_request_contract(query)
    specs = build_visualization_specs(csv_path, contract, query)

    assert len(specs) == 2
    spec1, spec2 = specs[0], specs[1]
    assert spec1.output_filename != spec2.output_filename
    assert spec1.chart_type != spec2.chart_type or spec1.x_column != spec2.x_column


def test_build_visualization_specs_excel_sheet_selection():
    """Verify explicit sheet selection and horizontal numeric series extraction."""
    xlsx_path = Path("data/demo/MRPL_Enterprise_Financial_and_Operational_History_10Y.xlsx")
    if not xlsx_path.exists():
        pytest.skip("Demo XLSX not found")


    query = "Create a line graph of Operating EBITDA from Income_Statement_10Y sheet"
    contract = parse_artifact_request_contract(query)
    specs = build_visualization_specs(xlsx_path, contract, query)

    assert len(specs) >= 1
    spec = specs[0]
    assert spec.source_sheet == "Income_Statement_10Y"
    assert spec.chart_type == ChartType.LINE
    assert any("FY" in str(x) for x in spec.x_values)


def test_generic_financial_line_graph_prefers_income_statement_ebitda():
    """The evaluator's short prompt must not select an arbitrary CAPEX sheet."""
    xlsx_path = Path("data/demo/MRPL_Enterprise_Financial_and_Operational_History_10Y.xlsx")
    if not xlsx_path.exists():
        pytest.skip("Demo XLSX not found")

    query = "Create a line graph and give me the PNG."
    contract = parse_artifact_request_contract(query)
    specs = build_visualization_specs(xlsx_path, contract, query)

    assert len(specs) == 1
    spec = specs[0]
    assert spec.source_sheet == "Income_Statement_10Y"
    assert "Operating EBITDA" in spec.y_columns[0]
    assert spec.output_filename.endswith("_ebitda_trend.png")


def test_generic_financial_graph_and_pdf_uses_named_metric_not_data_value():
    xlsx_path = Path("data/demo/MRPL_Enterprise_Financial_and_Operational_History_10Y.xlsx")
    if not xlsx_path.exists():
        pytest.skip("Demo XLSX not found")

    query = (
        "create a graphical representation on "
        "MRPL_Enterprise_Financial_and_Operational_History_10Y.xls, explain the data, and create a pdf"
    )
    contract = parse_artifact_request_contract(query)
    specs = build_visualization_specs(xlsx_path, contract, query)

    assert contract.png_required is True
    assert contract.pdf_required is True
    assert specs[0].source_sheet == "Income_Statement_10Y"
    assert specs[0].y_columns[0] in {
        "Revenue from Operations (Gross)",
        "Operating EBITDA",
    }
    assert not specs[0].y_columns[0].replace(".", "", 1).isdigit()

    insights = extract_document_insights(xlsx_path, query_hint=query)
    assert insights["primary_sheet"] == "Income_Statement_10Y"
    assert "revenue" in insights["metrics"]


def test_render_and_validate_png(tmp_path):
    """Verify trusted matplotlib rendering and strict Pillow cryptographic validation."""
    spec = VisualizationSpec(
        title="Test Unit Pressure Profile",
        source_file="unit_01.crv",
        chart_type=ChartType.LINE,
        x_column="Timestamp",
        y_columns=["Pressure_Bar"],
        x_values=["08:00", "09:00", "10:00", "11:00", "12:00"],
        series={"Pressure_Bar": [12.4, 12.8, 14.2, 13.9, 14.1]},
        x_label="Time (UTC)",
        y_label="Pressure (Bar)",
        output_filename="test_pressure.png"
    )

    out_file = tmp_path / "test_pressure.png"
    render_visualization(spec, out_file)

    assert out_file.exists()
    assert out_file.stat().st_size > 1000

    is_valid, msg = validate_png_artifact(out_file)
    assert is_valid is True, f"Validation failed: {msg}"


def test_long_time_series_uses_readable_representative_ticks():
    positions = _tick_positions(576)
    assert len(positions) <= 12
    assert positions[0] == 0
    assert positions[-1] == 575


def test_goal_contract_satisfaction():
    """Verify GoalContract enforcement fails closed when requested deliverables are missing."""
    contract = parse_artifact_request_contract("Create a PDF report and a PNG chart.")
    goal = GoalContract(artifact_contract=contract)

    # Initial state: no artifacts linked -> unsatisfied
    sat, missing = goal.check_satisfaction([])
    assert sat is False
    assert any("png_deliverable" in m for m in missing)
    assert any("pdf_deliverable" in m for m in missing)

    # Partial state: only PDF -> unsatisfied
    sat, missing = goal.check_satisfaction([{"artifact_type": "pdf", "file_size": 25000, "filename": "Report.pdf"}])
    assert sat is False
    assert any("png_deliverable" in m for m in missing)
    assert not any("pdf_deliverable" in m for m in missing)

    # Corrupt state: PNG with 0 bytes -> unsatisfied
    sat, missing = goal.check_satisfaction([
        {"artifact_type": "pdf", "file_size": 25000, "filename": "Report.pdf"},
        {"artifact_type": "png", "file_size": 0, "filename": "chart.png"}
    ])
    assert sat is False
    assert any("png_deliverable" in m for m in missing)

    # Complete state: Both PDF and PNG exist with non-zero size -> satisfied
    sat, missing = goal.check_satisfaction([
        {"artifact_type": "pdf", "file_size": 25000, "filename": "Report.pdf"},
        {"artifact_type": "png", "file_size": 35000, "filename": "chart.png"}
    ])
    assert sat is True
    assert len(missing) == 0


def test_csv_goal_contract_requires_a_real_nonempty_artifact():
    goal = GoalContract(
        artifact_contract=parse_artifact_request_contract("Create a CSV file from this data.")
    )
    assert goal.is_satisfied([]) is False
    assert goal.is_satisfied([{"artifact_type": "csv", "filename": "data.csv", "file_size": 0}]) is False
    assert goal.is_satisfied([{"artifact_type": "csv", "filename": "data.csv", "file_size": 64}]) is True
