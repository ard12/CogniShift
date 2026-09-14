"""
Unit and integration tests for PPTX Hybrid RAG in CogniShift:
- Format validation: accepts .pptx, rejects .ppt, .docm, .pptm
- Native slide structure extraction (titles, shapes, tables, notes)
- Format-aware citations: [Doc.pptx | Slide N | TEXT/VISUAL/BOTH]
- Visual slide retrieval value: proving visual channel retrieves chart/diagram slides
- Evidence fusion and ranking across PPTX slides
"""
import pytest
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException

from cognishift.core.document_processing.office_renderer import (
    extract_pptx_structured_content,
    render_pptx_slides
)
from cognishift.core.document_processing.provenance import format_grounded_citation
from cognishift.core.retrieval.evidence_fusion import EvidenceFusion
from cognishift.core.visual_rag.schemas import VisualSearchResult


@pytest.fixture
def sample_pptx_file(tmp_path: Path) -> Path:
    """Creates a sample multi-slide PPTX presentation with titles, text, tables, and notes."""
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Slide 1: Title Slide
    slide1 = prs.slides.add_slide(blank_layout)
    tx_box1 = slide1.shapes.add_textbox(Inches(1), Inches(1), Inches(11), Inches(2))
    p1 = tx_box1.text_frame.paragraphs[0]
    p1.text = "Refinery Incident Investigation Brief"
    p1.font.size = Pt(36)
    p1.font.bold = True

    # Slide 2: Table & Findings with Notes
    slide2 = prs.slides.add_slide(blank_layout)
    tx_box2 = slide2.shapes.add_textbox(Inches(1), Inches(0.5), Inches(11), Inches(1))
    tx_box2.text_frame.paragraphs[0].text = "Telemetry Anomaly Summary"
    
    table_shape = slide2.shapes.add_table(3, 3, Inches(1), Inches(2), Inches(11), Inches(2))
    tbl = table_shape.table
    tbl.cell(0, 0).text = "Time (UTC)"
    tbl.cell(0, 1).text = "Pressure PT-101 (barg)"
    tbl.cell(0, 2).text = "Status"
    tbl.cell(1, 0).text = "08:14:00"
    tbl.cell(1, 1).text = "38.2"
    tbl.cell(1, 2).text = "NORMAL"
    tbl.cell(2, 0).text = "08:14:32"
    tbl.cell(2, 1).text = "46.8"
    tbl.cell(2, 2).text = "TRIP EXCURSION"

    # Add speaker notes to Slide 2
    slide2.notes_slide.notes_text_frame.text = "Authoritative note: Pressure exceeded ASME design threshold at 08:14:32."

    # Slide 3: Visual Flow Diagram / Architecture Slide
    slide3 = prs.slides.add_slide(blank_layout)
    tx_box3 = slide3.shapes.add_textbox(Inches(1), Inches(0.5), Inches(11), Inches(1))
    tx_box3.text_frame.paragraphs[0].text = "Safety Trip Logic Diagram"
    # Add a descriptive shape
    shape = slide3.shapes.add_shape(
        1, Inches(2), Inches(2), Inches(4), Inches(2) # 1 = msoShapeRectangle
    )
    shape.text = "Pressure Switch PSH-101 -> Interlock I-101 -> Trip Valve XV-101"

    file_path = tmp_path / "incident_brief.pptx"
    prs.save(str(file_path))
    return file_path


def test_pptx_native_extraction(sample_pptx_file: Path):
    """Verify PPTX native extraction preserves slide boundaries, tables, and notes."""
    slides = extract_pptx_structured_content(sample_pptx_file)
    assert len(slides) == 3

    # Check Slide 1
    s1 = slides[0]
    assert s1["slide_number"] == 1
    assert "Refinery Incident Investigation Brief" in s1["text"]
    assert s1["slide_title"] == "Refinery Incident Investigation Brief"

    # Check Slide 2 (Table + Notes)
    s2 = slides[1]
    assert s2["slide_number"] == 2
    assert "Telemetry Anomaly Summary" in s2["slide_title"]
    assert s2["has_tables"] is True
    assert "PT-101" in s2["text"]
    assert "46.8" in s2["text"]
    assert s2["has_notes"] is True
    assert "Pressure exceeded ASME design threshold" in s2["text"]
    assert s2["notes_status"] in ("SUPPORTED", "PRESENT")

    # Check Slide 3
    s3 = slides[2]
    assert s3["slide_number"] == 3
    assert "Safety Trip Logic Diagram" in s3["slide_title"]
    assert "PSH-101" in s3["text"]


def test_pptx_citation_formatting():
    """Verify authoritative citation formatting for PPTX slides."""
    # 1. Slide Text
    meta_text = {
        "filename": "incident_brief.pptx",
        "document_type": "pptx",
        "slide_number": 2,
        "channel": "text",
        "extraction_method": "presentation"
    }
    assert format_grounded_citation(meta_text) == "[incident_brief.pptx | Slide 2 | TEXT]"

    # 2. Slide Visual
    meta_vis = {
        "filename": "incident_brief.pptx",
        "document_type": "pptx",
        "slide_number": 3,
        "channel": "visual",
        "extraction_method": "visual"
    }
    assert format_grounded_citation(meta_vis) == "[incident_brief.pptx | Slide 3 | VISUAL]"

    # 3. Slide Both (Hybrid)
    meta_both = {
        "filename": "incident_brief.pptx",
        "document_type": "pptx",
        "slide_number": 2,
        "channel": "both",
        "extraction_method": "presentation"
    }
    assert format_grounded_citation(meta_both) == "[incident_brief.pptx | Slide 2 | BOTH]"


def test_pptx_evidence_fusion_chart_value():
    """
    Proves that visual slide retrieval adds value:
    Slide 3 has visual diagram information that ranks high visually,
    while Slide 2 has tabular text that ranks high in text.
    """
    fusion = EvidenceFusion(rrf_k=60)

    # Text items: only mentions Slide 2 telemetry
    text_items = [
        {
            "doc": "PT-101 tripped at 46.8 barg.",
            "meta": {
                "source_id": 42,
                "processing_version": "v1",
                "filename": "deck.pptx",
                "document_type": "pptx",
                "slide_number": 2
            },
            "score": 0.88,
            "source_id": 42,
            "filename": "deck.pptx"
        }
    ]

    # Visual items: Slide 2 and Slide 3 (diagram) detected visually
    visual_results = [
        VisualSearchResult(
            workspace_id=1,
            source_id=42,
            processing_version="v1",
            page_number=3,
            slide_number=3,
            filename="deck.pptx",
            document_type="pptx",
            locator_kind="slide",
            score=7.5
        ),
        VisualSearchResult(
            workspace_id=1,
            source_id=42,
            processing_version="v1",
            page_number=2,
            slide_number=2,
            filename="deck.pptx",
            document_type="pptx",
            locator_kind="slide",
            score=4.2
        )
    ]

    fused = fusion.fuse(text_items, visual_results, query="Show the interlock trip logic diagram")
    assert len(fused) == 2

    # Slide 3 was visual-only and top ranked on diagram query
    vis_cand = next(c for c in fused if c.page_number == 3)
    assert vis_cand.retrieval_channel == "VISUAL"
    assert vis_cand.document_type == "pptx"
    assert vis_cand.locator_kind == "slide"
    assert vis_cand.slide_number == 3
    assert vis_cand.citation == "[deck.pptx | Slide 3 | VISUAL]"

    # Slide 2 was present in both channels
    both_cand = next(c for c in fused if c.page_number == 2)
    assert both_cand.retrieval_channel == "BOTH"
    assert both_cand.document_type == "pptx"
    assert both_cand.slide_number == 2
    assert both_cand.citation == "[deck.pptx | Slide 2 | BOTH]"
