"""
Automated validation suite for newly generated industrial test assets:
1. High-precision OCR images (PT-101 gauge, TT-204 meter, K-101 nameplate, MOV-101 calibration tag).
2. Multi-page technical SOP PDF document (K-101 Compressor Standard Operating Procedure).
3. 24-hour SCADA telemetry dataset and deterministic visualization generation.
"""
import pytest
from pathlib import Path
from pypdf import PdfReader
from PIL import Image

from cognishift.core.document_processing.ocr_provider import RapidOCREngine
from cognishift.core.visualization.schemas import ChartType
from cognishift.core.visualization.selector import parse_artifact_request_contract, build_visualization_specs
from cognishift.core.visualization.renderer import render_visualization
from cognishift.core.visualization.validator import validate_png_artifact


DEMO_DIR = Path("data/demo")


@pytest.mark.asyncio
async def test_ocr_extraction_on_industrial_gauge():
    """Verify RapidOCR extracts PT-101 discharge pressure dial markings."""
    img_path = DEMO_DIR / "gauge_compressor_discharge_pt101.png"
    assert img_path.exists(), "Gauge test image must exist"

    engine = RapidOCREngine()
    res = await engine.extract(img_path.read_bytes())

    assert res.engine == "rapidocr"
    assert res.confidence is not None and res.confidence > 0.70
    text_clean = res.text.replace(" ", "").upper()
    assert "PT-101" in text_clean
    assert "DISCHARGE" in text_clean
    assert "PRESSURE" in text_clean
    assert "BAR" in text_clean
    assert len(res.blocks) >= 10


@pytest.mark.asyncio
async def test_ocr_extraction_on_digital_panel_meter():
    """Verify RapidOCR extracts TT-204 LED display and temperature reading."""
    img_path = DEMO_DIR / "digital_panel_meter_tt204.png"
    assert img_path.exists(), "Digital panel meter test image must exist"

    engine = RapidOCREngine()
    res = await engine.extract(img_path.read_bytes())

    assert res.confidence is not None and res.confidence > 0.70
    text_clean = res.text.replace(" ", "").upper()
    assert "TT-204" in text_clean
    assert "87.4" in text_clean
    assert any(k in text_clean for k in ["YOKOGAWA", "STATUS", "NORMAL", "SETPOINT"])


@pytest.mark.asyncio
async def test_ocr_extraction_on_equipment_nameplate():
    """Verify RapidOCR extracts stamped equipment specifications on K-101 nameplate."""
    img_path = DEMO_DIR / "nameplate_compressor_k101.png"
    assert img_path.exists(), "Nameplate test image must exist"

    engine = RapidOCREngine()
    res = await engine.extract(img_path.read_bytes())

    assert res.confidence is not None and res.confidence > 0.70
    text_clean = res.text.replace(" ", "").upper()
    assert "K-101" in text_clean
    assert any(k in text_clean for k in ["EBARA", "ELLIOTT", "COMPRESSOR"])
    assert any(k in text_clean for k in ["32.5", "68.2", "11,200", "4,200"])


@pytest.mark.asyncio
async def test_ocr_extraction_on_calibration_tag():
    """Verify RapidOCR extracts MOV-101 inspection dates, technician and supervisor status."""
    img_path = DEMO_DIR / "calibration_tag_mov101.png"
    assert img_path.exists(), "Calibration tag test image must exist"

    engine = RapidOCREngine()
    res = await engine.extract(img_path.read_bytes())

    assert res.confidence is not None and res.confidence > 0.85
    text_clean = res.text.replace(" ", "").upper()
    assert "MOV-101" in text_clean
    assert any(k in text_clean for k in ["CALIBRATION", "INSPECTION", "ROTORK", "STROKE", "VERIFIED"])
    assert any(k in text_clean for k in ["VICKY", "SUPERVISOR", "SAMUEL"])


def test_sop_pdf_structure_and_governance_content():
    """Verify newly generated K-101 SOP PDF document contains 2 pages and governance sections."""
    pdf_path = DEMO_DIR / "K-101_Compressor_Standard_Operating_Procedure_and_Emergency_Trip.pdf"
    assert pdf_path.exists(), "SOP PDF must exist"

    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) == 2, "SOP PDF must be exactly 2 pages"

    page1_text = reader.pages[0].extract_text()
    page2_text = reader.pages[1].extract_text()
    full_text = page1_text + " " + page2_text

    # Verify equipment tags & envelope
    assert "K-101" in full_text
    assert "MOV-101" in full_text
    assert "30.0 - 35.0" in full_text
    assert "64.0 - 70.0" in full_text
    assert "TT-204" in full_text

    # Verify Four-Eyes Authorization & Safety sections
    assert "Four-Eyes" in full_text or "Dual Supervisor" in full_text
    assert "restart_service" in full_text
    assert "Flare-Header" in full_text


def test_telemetry_dataset_integrity():
    """Verify K-101 telemetry CSV has 144 rows and correct numeric structure."""
    csv_path = DEMO_DIR / "compressor_k101_telemetry_24h.csv"
    assert csv_path.exists(), "Telemetry CSV must exist"

    import csv
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    assert len(reader) == 144

    for row in reader:
        assert row["component_id"] == "K-101"
        assert float(row["discharge_pressure_bar"]) > 60.0
        assert float(row["suction_pressure_bar"]) > 28.0
        assert float(row["vibration_rms_mm_s"]) > 1.0
        assert float(row["bearing_temperature_c"]) > 70.0


def test_telemetry_visualization_generation(tmp_path):
    """Verify deterministic generation and structural validation of K-101 charts."""
    csv_path = DEMO_DIR / "compressor_k101_telemetry_24h.csv"
    
    # 1. Line chart
    query_line = "Create a line chart showing the discharge pressure of K-101 over time from the attached CSV."
    contract_line = parse_artifact_request_contract(query_line)
    specs_line = build_visualization_specs(csv_path, contract_line, query_line)
    assert len(specs_line) == 1
    assert specs_line[0].chart_type == ChartType.LINE

    out_line = tmp_path / "k101_discharge_test.png"
    render_visualization(specs_line[0], out_line)
    assert out_line.exists()
    is_valid, msg = validate_png_artifact(out_line)
    assert is_valid is True

    # 2. Bar chart from multi-sheet XLSX
    xlsx_path = DEMO_DIR / "compressor_k101_telemetry_24h.xlsx"
    query_bar = "Create a bar chart of peak values from Alarm Summary."
    contract_bar = parse_artifact_request_contract(query_bar)
    specs_bar = build_visualization_specs(xlsx_path, contract_bar, query_bar)
    assert len(specs_bar) == 1
    assert specs_bar[0].chart_type == ChartType.BAR

    out_bar = tmp_path / "k101_alarms_test.png"
    render_visualization(specs_bar[0], out_bar)
    assert out_bar.exists()
    is_valid_bar, msg_bar = validate_png_artifact(out_bar)
    assert is_valid_bar is True
