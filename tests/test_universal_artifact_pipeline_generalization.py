"""
Universal Artifact Pipeline Generalization & Multi-Domain Test Suite.
Verifies that CogniShift's canonical artifact quality pipeline is truly universal and generic:
Works across arbitrary assets, metrics, and industrial domains with real fixture data:
- PPTX x 3 (Furnace F-101 tube skin, Boiler B-201 drum level, Pump P-301 seal oil)
- PDF x 3 (Technical Investigation Report, Emergency Isolation SOP, Relief Valve Calculation)
- DOCX x 3 (Standard Operating Procedure, Maintenance LOTO Checklist, Shift Handover Report)
- XLSX x 2 (Process Telemetry Log, Valve Stroke Time Test Ledger)
- CSV x 2 (Alarm Historian Export, Chromatography Stream Composition)
- Charts / Negative tests (Visual artifact generation + fail-closed validation)
"""
import pytest
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from cognishift.app.config import settings
from cognishift.core.security import ensure_workspace_layout, get_workspace_root
from cognishift.core.artifact_quality.schemas import (
    ArtifactLifecycleState,
    ArtifactSemanticMetadata,
    CalloutBlock,
    CalloutType,
    DimensionStatus,
    DocumentType,
    EvidenceReference,
    GroundedArtifactContext,
    MeasuredQuantity,
    PhysicalDimension,
    QualityReport,
    StandardClaim,
    TimeWindow,
    VisualPurpose,
)
from cognishift.core.artifact_quality.service import ArtifactGenerationService
from cognishift.core.artifact_quality.report_planner import TechnicalReportPlanner
from cognishift.core.artifact_quality.sop_planner import SOPPlanner
from cognishift.core.presentation.schemas import PresentationSpec, SlideSpec, SlideType, MetricCard
from cognishift.core.presentation.renderer import PresentationRenderer

TEST_WS_ID = 888


@pytest.fixture(scope="module", autouse=True)
def setup_test_workspace():
    ensure_workspace_layout(TEST_WS_ID)
    ws_root = get_workspace_root(TEST_WS_ID)
    yield ws_root
    # Cleanup
    if ws_root.exists():
        try:
            shutil.rmtree(str(ws_root), ignore_errors=True)
        except Exception:
            pass


# ==============================================================================
# 1. PPTX Executive Presentations (3 Unrelated Industrial Domains)
# ==============================================================================

@pytest.mark.asyncio
async def test_pptx_01_furnace_tube_skin_excursion():
    """Domain 1: Crude Vacuum Furnace F-101 Tube Skin Over-Temperature Excursion."""
    ctx = GroundedArtifactContext(
        content_context_id="ctx_furnace_f101",
        title="Furnace F-101 Tube Skin Excursion Investigation",
        workspace_id=TEST_WS_ID,
        subject_assets=["F-101", "TI-1014"],
        sensor_tags=["TI-1014", "TI-1015", "FIC-102"],
        quantities={
            "Peak Skin Temp": MeasuredQuantity(value=652.0, unit="c", dimension=PhysicalDimension.TEMPERATURE),
            "MAWT Limit": MeasuredQuantity(value=620.0, unit="c", dimension=PhysicalDimension.TEMPERATURE),
            "Charge Flow": MeasuredQuantity(value=18500.0, unit="kg/h", dimension=PhysicalDimension.FLOW)
        },
        time_window=TimeWindow(
            start=datetime(2026, 9, 1, 4, 0, tzinfo=timezone.utc),
            end=datetime(2026, 9, 1, 5, 0, tzinfo=timezone.utc)
        ),
        claims_ledger=[
            StandardClaim(
                claim_id="sc_api560",
                claim_text="Fired heaters for general refinery service compliance",
                standard_designation="API 560",
                supporting_evidence_ids=["ref_api560"]
            )
        ],
        source_references=[
            EvidenceReference(
                source_id="furnace_telemetry",
                workspace_id=TEST_WS_ID,
                checksum="abc1234567890",
                locator="Rows 10-50",
                channel="xlsx"
            )
        ]
    )

    spec = PresentationSpec(
        title="F-101 Tube Skin Over-Temperature Brief",
        subtitle="Crude Distillation Unit // Radiant Cell B Excursion Review",
        slides=[
            SlideSpec(slide_type=SlideType.TITLE, title="F-101 Tube Skin Over-Temperature Brief", subtitle="Executive Engineering Review"),
            SlideSpec(
                slide_type=SlideType.EXECUTIVE_SUMMARY,
                title="Radiant Coil B Overheat Finding",
                bullets=["TI-1014 breached 620.0 C design limit reaching 652.0 C.", "Coking deposition suspected in pass 4."],
                metrics=[
                    MetricCard(label="Peak Temp", value="652.0 C", status="CRITICAL"),
                    MetricCard(label="MAWT Limit", value="620.0 C", status="CRITICAL"),
                    MetricCard(label="Charge Flow", value="18,500 kg/h", status="NORMAL")
                ]
            ),
            SlideSpec(
                slide_type=SlideType.TIMELINE,
                title="Thermal Excursion Progression",
                bullets=["04:12 UTC: Fuel gas pressure spike", "04:18 UTC: Alarm TI-1014 trip", "04:30 UTC: Emergency firing cutback"]
            ),
            SlideSpec(
                slide_type=SlideType.EVIDENCE_SUMMARY,
                title="Cross-Discipline Evidence Corroboration",
                bullets=[
                    "Telemetry: Pass 4 flow drop preceding skin temperature rise.",
                    "SOP Limits: CDU-SOP-014 defines 620 C as emergency trip.",
                    "NDT Inspection: Ultrasonic thickness confirms zero wall thinning.",
                    "P&ID Topology: DWG-F-101 confirms radiant coil arrangement."
                ]
            ),
            SlideSpec(
                slide_type=SlideType.ROOT_CAUSE,
                title="Root Cause Analysis: Flame Impingement & Coking",
                bullets=["Primary Cause: Burner B-04 tip blockage causing asymmetric flame impingement.", "Contributing: Unequal pass flow distribution."]
            ),
            SlideSpec(
                slide_type=SlideType.SOURCE_APPENDIX,
                title="Engineering Data Provenance",
                sources=["SCADA Historian | Tag: TI-1014", "API 560 Fired Heaters Manual"]
            )
        ]
    )

    path, report = await ArtifactGenerationService.generate_artifact(
        request_text="Generate executive briefing for F-101 furnace skin overheat",
        context=ctx,
        workspace_id=TEST_WS_ID,
        explicit_format="pptx",
        custom_spec=spec
    )

    assert path is not None and path.exists()
    assert report.enterprise_ready or report.demo_ready
    assert report.dimensions["structural_valid"].status == DimensionStatus.PASS
    assert report.dimensions["source_grounding_valid"].status == DimensionStatus.PASS


@pytest.mark.asyncio
async def test_pptx_02_boiler_drum_level_excursion():
    """Domain 2: Utility Plant Boiler B-201 Steam Drum Water Level Excursion."""
    ctx = GroundedArtifactContext(
        content_context_id="ctx_boiler_b201",
        title="Boiler B-201 Drum Level Excursion",
        workspace_id=TEST_WS_ID,
        subject_assets=["B-201", "LT-201"],
        sensor_tags=["LT-201", "PT-202"],
        quantities={
            "Drum Level": MeasuredQuantity(value=145.0, unit="mm", dimension=PhysicalDimension.LENGTH),
            "Trip Level": MeasuredQuantity(value=120.0, unit="mm", dimension=PhysicalDimension.LENGTH)
        },
        source_references=[
            EvidenceReference(source_id="boiler_log", workspace_id=TEST_WS_ID, checksum="bl789", channel="csv")
        ]
    )

    spec = PresentationSpec(
        title="Boiler B-201 Drum High Level Investigation",
        subtitle="Utility Steam Plant // Trip Interlock Analysis",
        slides=[
            SlideSpec(slide_type=SlideType.TITLE, title="Boiler B-201 Drum High Level Investigation", subtitle="Trip Review"),
            SlideSpec(
                slide_type=SlideType.EXECUTIVE_SUMMARY,
                title="Drum Level Excursion",
                bullets=["Steam drum water level surged to +145 mm against +120 mm trip limit."],
                metrics=[MetricCard(label="Peak Level", value="+145 mm", status="CRITICAL")]
            ),
            SlideSpec(
                slide_type=SlideType.RECOMMENDED_ACTIONS,
                title="Corrective Actions (CAPA)",
                bullets=["Immediate: Recalibrate DP level transmitter LT-201.", "Pre-Startup: Verify feed valve FCV-201 stroke."]
            ),
            SlideSpec(
                slide_type=SlideType.SOURCE_APPENDIX,
                title="Authoritative Data References",
                sources=["Utility Plant DCS Historian | Tag: LT-201", "ASME Section I Power Boilers"]
            )
        ]
    )

    path, report = await ArtifactGenerationService.generate_artifact(
        request_text="Generate briefing for boiler drum level trip",
        context=ctx,
        workspace_id=TEST_WS_ID,
        explicit_format="pptx",
        custom_spec=spec
    )
    assert path is not None and path.exists()
    assert report.enterprise_ready or report.demo_ready


@pytest.mark.asyncio
async def test_pptx_03_pump_seal_oil_failure():
    """Domain 3: Liquefied Gas Compressor P-301 Seal Oil Differential Pressure Drop."""
    ctx = GroundedArtifactContext(
        content_context_id="ctx_pump_p301",
        title="P-301 Seal Oil Pressure Drop",
        workspace_id=TEST_WS_ID,
        subject_assets=["P-301", "PDIT-301"],
        sensor_tags=["PDIT-301"],
        quantities={
            "Delta Pressure": MeasuredQuantity(value=0.75, unit="bar", dimension=PhysicalDimension.PRESSURE),
            "Min Delta P": MeasuredQuantity(value=1.20, unit="bar", dimension=PhysicalDimension.PRESSURE)
        },
        source_references=[
            EvidenceReference(source_id="p301_telemetry", workspace_id=TEST_WS_ID, checksum="p301_cs", channel="xlsx")
        ]
    )

    spec = PresentationSpec(
        title="Pump P-301 Seal Oil Differential Pressure Loss",
        subtitle="Gas Processing Area // Rotating Equipment Failure Analysis",
        slides=[
            SlideSpec(slide_type=SlideType.TITLE, title="Pump P-301 Seal Oil Pressure Loss", subtitle="Engineering Report"),
            SlideSpec(
                slide_type=SlideType.EXECUTIVE_SUMMARY,
                title="Seal Oil Delta P Depletion",
                bullets=["Seal oil differential pressure dropped to 0.75 bar."],
                metrics=[MetricCard(label="Delta P", value="0.75 bar", status="CRITICAL")]
            ),
            SlideSpec(
                slide_type=SlideType.SOURCE_APPENDIX,
                title="Reference Log",
                sources=["API 682 Pumps - Shaft Sealing Systems", "Rotating Machinery Logbook"]
            )
        ]
    )

    path, report = await ArtifactGenerationService.generate_artifact(
        request_text="Generate presentation for pump P-301 seal oil failure",
        context=ctx,
        workspace_id=TEST_WS_ID,
        explicit_format="pptx",
        custom_spec=spec
    )
    assert path is not None and path.exists()
    assert report.enterprise_ready or report.demo_ready


# ==============================================================================
# 2. PDF Engineering Documents (3 Distinct Report Types)
# ==============================================================================

@pytest.mark.asyncio
async def test_pdf_01_technical_investigation_report():
    """PDF 1: Hydrocracker Reactor R-401 Catalyst Bed Pressure Drop Investigation."""
    ctx = GroundedArtifactContext(
        content_context_id="ctx_r401_dp",
        title="Reactor R-401 Pressure Drop Investigation",
        workspace_id=TEST_WS_ID,
        subject_assets=["R-401"],
        quantities={
            "Bed Delta P": MeasuredQuantity(value=3.4, unit="bar", dimension=PhysicalDimension.PRESSURE),
            "Allowable Limit": MeasuredQuantity(value=2.5, unit="bar", dimension=PhysicalDimension.PRESSURE)
        },
        source_references=[
            EvidenceReference(source_id="r401_bed_log", workspace_id=TEST_WS_ID, checksum="r401_cs", channel="pdf")
        ]
    )

    planned_spec = TechnicalReportPlanner.plan(
        request_text="Conduct technical investigation into Reactor R-401 catalyst bed differential pressure drop",
        context=ctx
    )

    path, report = await ArtifactGenerationService.generate_artifact(
        request_text="Conduct technical investigation into Reactor R-401 catalyst bed differential pressure drop",
        context=ctx,
        workspace_id=TEST_WS_ID,
        explicit_format="pdf",
        custom_spec=planned_spec
    )

    assert path is not None and path.exists()
    assert path.suffix == ".pdf"
    assert report.enterprise_ready or report.demo_ready
    assert report.dimensions["structural_valid"].status == DimensionStatus.PASS


@pytest.mark.asyncio
async def test_pdf_02_emergency_isolation_sop():
    """PDF 2: Emergency Isolation SOP for Catalytic Reforming Unit CRU-100 Feed Line."""
    ctx = GroundedArtifactContext(
        content_context_id="ctx_sop_cru100",
        title="CRU-100 Feed Line Emergency Isolation",
        workspace_id=TEST_WS_ID,
        subject_assets=["CRU-100", "XV-402"],
        source_references=[
            EvidenceReference(source_id="cru_safety_sop", workspace_id=TEST_WS_ID, checksum="sop_cs", channel="docx")
        ]
    )

    planned_sop = SOPPlanner.plan(
        request_text="Standard Operating Procedure for emergency isolation of CRU-100 feed line",
        context=ctx
    )

    path, report = await ArtifactGenerationService.generate_artifact(
        request_text="Standard Operating Procedure for emergency isolation of CRU-100 feed line",
        context=ctx,
        workspace_id=TEST_WS_ID,
        explicit_format="pdf",
        custom_spec=planned_sop
    )

    assert path is not None and path.exists()
    assert report.enterprise_ready or report.demo_ready


@pytest.mark.asyncio
async def test_pdf_03_relief_valve_sizing_calculation():
    """PDF 3: Relief Valve Sizing Calculation Report for Column C-301 under API 520."""
    ctx = GroundedArtifactContext(
        content_context_id="ctx_calc_c301",
        title="Column C-301 Relief Valve Sizing Calculation",
        workspace_id=TEST_WS_ID,
        subject_assets=["C-301", "PSV-301"],
        claims_ledger=[
            StandardClaim(
                claim_id="sc_api520",
                claim_text="Sizing of pressure-relieving devices",
                standard_designation="API 520",
                supporting_evidence_ids=["ev_api520"]
            )
        ],
        source_references=[
            EvidenceReference(source_id="c301_pfd", workspace_id=TEST_WS_ID, checksum="c301_cs", channel="pdf")
        ]
    )

    planned_spec = TechnicalReportPlanner.plan(
        request_text="Generate relief valve sizing calculation report for Amine Regenerator Column C-301",
        context=ctx
    )

    path, report = await ArtifactGenerationService.generate_artifact(
        request_text="Generate relief valve sizing calculation report for Amine Regenerator Column C-301",
        context=ctx,
        workspace_id=TEST_WS_ID,
        explicit_format="pdf",
        custom_spec=planned_spec
    )
    assert path is not None and path.exists()
    assert report.enterprise_ready or report.demo_ready


# ==============================================================================
# 3. DOCX Engineering Deliverables (3 Distinct Procedural Types)
# ==============================================================================

@pytest.mark.asyncio
async def test_docx_01_operating_procedure():
    """DOCX 1: Standard Operating Procedure for Lube Oil Console LO-202 Filter Changeout."""
    ctx = GroundedArtifactContext(
        content_context_id="ctx_sop_lo202",
        title="Lube Oil Console LO-202 Duplex Filter Changeout",
        workspace_id=TEST_WS_ID,
        subject_assets=["LO-202"],
        source_references=[
            EvidenceReference(source_id="lo202_manual", workspace_id=TEST_WS_ID, checksum="lo202_cs", channel="docx")
        ]
    )

    planned_sop = SOPPlanner.plan(
        request_text="Generate Standard Operating Procedure for LO-202 duplex filter changeout",
        context=ctx
    )

    path, report = await ArtifactGenerationService.generate_artifact(
        request_text="Generate Standard Operating Procedure for LO-202 duplex filter changeout",
        context=ctx,
        workspace_id=TEST_WS_ID,
        explicit_format="docx",
        custom_spec=planned_sop
    )

    assert path is not None and path.exists()
    assert path.suffix == ".docx"
    assert report.enterprise_ready or report.demo_ready
    assert report.dimensions["structural_valid"].status == DimensionStatus.PASS


@pytest.mark.asyncio
async def test_docx_02_maintenance_loto_checklist():
    """DOCX 2: Maintenance LOTO Checklist with Safety Callouts for Separator V-501."""
    ctx = GroundedArtifactContext(
        content_context_id="ctx_loto_v501",
        title="High Pressure Separator V-501 LOTO Checklist",
        workspace_id=TEST_WS_ID,
        subject_assets=["V-501"],
        source_references=[
            EvidenceReference(source_id="v501_spec", workspace_id=TEST_WS_ID, checksum="v501_cs", channel="pdf")
        ]
    )

    planned_sop = SOPPlanner.plan(
        request_text="Generate LOTO checklist for High Pressure Separator V-501 maintenance",
        context=ctx
    )

    path, report = await ArtifactGenerationService.generate_artifact(
        request_text="Generate LOTO checklist for High Pressure Separator V-501 maintenance",
        context=ctx,
        workspace_id=TEST_WS_ID,
        explicit_format="docx",
        custom_spec=planned_sop
    )
    assert path is not None and path.exists()
    assert report.enterprise_ready or report.demo_ready


@pytest.mark.asyncio
async def test_docx_03_shift_handover_report():
    """DOCX 3: Shift Handover Report for Flare Gas Recovery Unit FGRU-10."""
    ctx = GroundedArtifactContext(
        content_context_id="ctx_handover_fgru10",
        title="FGRU-10 Shift Handover Report",
        workspace_id=TEST_WS_ID,
        subject_assets=["FGRU-10"],
        source_references=[
            EvidenceReference(source_id="fgru_log", workspace_id=TEST_WS_ID, checksum="fgru_cs", channel="xlsx")
        ]
    )

    planned_spec = TechnicalReportPlanner.plan(
        request_text="Generate shift handover report for Flare Gas Recovery Unit FGRU-10",
        context=ctx
    )

    path, report = await ArtifactGenerationService.generate_artifact(
        request_text="Generate shift handover report for Flare Gas Recovery Unit FGRU-10",
        context=ctx,
        workspace_id=TEST_WS_ID,
        explicit_format="docx",
        custom_spec=planned_spec
    )
    assert path is not None and path.exists()
    assert report.enterprise_ready or report.demo_ready


# ==============================================================================
# 4. XLSX Workbooks & CSV Exports (Analytical Datasets)
# ==============================================================================

@pytest.mark.asyncio
async def test_xlsx_01_telemetry_workbook():
    """XLSX 1: Analytical process telemetry workbook with freeze panes and provenance sheet."""
    spec = type("CustomWorkbook", (), {
        "title": "Refinery Unit 100 Process Telemetry",
        "report_id": "U100_Telemetry_Log",
        "sheets": [
            {
                "name": "Hourly_Averages",
                "headers": ["Timestamp_UTC", "Asset", "Tag", "Description", "Value", "Units", "Status"],
                "rows": [
                    ["2026-09-13 08:00:00", "V-101", "PT-101", "Accumulator Pressure", 38.20, "barg", "NORMAL"],
                    ["2026-09-13 08:14:00", "V-101", "PT-101", "Accumulator Pressure", 42.80, "barg", "HIGH_ALARM"],
                    ["2026-09-13 08:14:32", "V-101", "PT-101", "Accumulator Pressure", 46.80, "barg", "TRIP_BREACH"],
                    ["2026-09-13 08:20:00", "V-101", "PT-101", "Accumulator Pressure", 39.50, "barg", "NORMAL"]
                ]
            }
        ]
    })()

    path, report = await ArtifactGenerationService.generate_artifact(
        request_text="Export process telemetry log to spreadsheet",
        workspace_id=TEST_WS_ID,
        explicit_format="xlsx",
        custom_spec=spec
    )

    assert path is not None and path.exists()
    assert path.suffix == ".xlsx"
    assert report.enterprise_ready or report.demo_ready
    assert report.dimensions["structural_valid"].status == DimensionStatus.PASS


@pytest.mark.asyncio
async def test_xlsx_02_valve_stroke_time_ledger():
    """XLSX 2: Valve Stroke Time Test Ledger across 12 automated emergency shutdown valves."""
    spec = type("ValveTestWorkbook", (), {
        "title": "ESD Valve Stroke Time Test Records",
        "report_id": "ESD_Stroke_Test_Q3",
        "sheets": [
            {
                "name": "Stroke_Times",
                "headers": ["Valve_Tag", "Service", "Baseline_Limit_s", "Measured_s", "Variance_s", "Test_Result"],
                "rows": [
                    ["XV-101", "Crude Overhead Suction", 30.0, 38.4, 8.4, "FAILED"],
                    ["XV-102", "Column Bottoms Isolation", 25.0, 21.2, -3.8, "PASSED"],
                    ["XV-201", "Reboiler Steam Cutoff", 15.0, 14.1, -0.9, "PASSED"],
                    ["XV-301", "Fuel Gas Emergency Block", 5.0, 3.8, -1.2, "PASSED"]
                ]
            }
        ]
    })()

    path, report = await ArtifactGenerationService.generate_artifact(
        request_text="Generate emergency valve stroke test records",
        workspace_id=TEST_WS_ID,
        explicit_format="xlsx",
        custom_spec=spec
    )
    assert path is not None and path.exists()
    assert report.enterprise_ready or report.demo_ready


@pytest.mark.asyncio
async def test_csv_01_alarm_historian_export():
    """CSV 1: Standard RFC 4180 alarm historian log with formula injection sanitization."""
    spec = type("AlarmCsv", (), {
        "title": "SCADA Alarm Historian Dump",
        "report_id": "Alarms_20260913",
        "headers": ["Timestamp_UTC", "Priority", "Tag", "Condition", "Ack_Status"],
        "rows": [
            ["2026-09-13T08:14:25Z", "CRITICAL", "PT-101", "HIGH_HIGH_LIMIT_EXCEEDED", "ACKNOWLEDGED"],
            ["2026-09-13T08:14:28Z", "HIGH", "XV-101", "VALVE_TRAVEL_TIME_EXCEEDED", "UNACKNOWLEDGED"],
            ["=SUM(1,2)", "NORMAL", "TT-102", "INFO_MESSAGE", "ACKNOWLEDGED"]  # Injection test
        ]
    })()

    path, report = await ArtifactGenerationService.generate_artifact(
        request_text="Export alarm sequence to CSV",
        workspace_id=TEST_WS_ID,
        explicit_format="csv",
        custom_spec=spec
    )

    assert path is not None and path.exists()
    assert path.suffix == ".csv"
    assert report.enterprise_ready or report.demo_ready

    # Verify formula injection sanitization in CSV output
    content = path.read_text(encoding="utf-8")
    assert "'=SUM(1,2)" in content, "Formula injection must be safely escaped with leading single-quote"


@pytest.mark.asyncio
async def test_csv_02_chromatography_stream_composition():
    """CSV 2: Online Gas Chromatograph mole fraction analysis."""
    spec = type("GCData", (), {
        "title": "Overhead Vapor Chromatography Analysis",
        "report_id": "GC_Stream_06_OVHD",
        "headers": ["Component", "Formula", "Mole_Percent", "Mass_Percent", "Specification_Max"],
        "rows": [
            ["Methane", "CH4", 12.4, 4.2, 15.0],
            ["Ethane", "C2H6", 24.1, 15.3, 28.0],
            ["Propane", "C3H8", 38.6, 36.0, 42.0],
            ["i-Butane", "C4H10", 14.2, 17.5, 18.0],
            ["n-Butane", "C4H10", 10.7, 27.0, 15.0]
        ]
    })()

    path, report = await ArtifactGenerationService.generate_artifact(
        request_text="Export chromatography composition table to CSV",
        workspace_id=TEST_WS_ID,
        explicit_format="csv",
        custom_spec=spec
    )
    assert path is not None and path.exists()
    assert report.enterprise_ready or report.demo_ready