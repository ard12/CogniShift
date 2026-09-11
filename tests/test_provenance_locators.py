"""
Unit tests for format-aware citations (PDF, XLSX, DOCX) and multi-page citation non-collapsing.
"""
import pytest
from cognishift.core.document_processing.provenance import (
    format_grounded_citation,
    extract_and_normalize_citations,
    reconcile_citations_against_evidence
)


def test_multi_page_citation_reconciliation_preserves_all_pages():
    """Verify that multiple pages from the same document (e.g. Page 16 and Page 32) are NEVER collapsed."""
    evidence = [
        {"filename": "Pumps_Manual.pdf", "page": 16, "extraction_method": "NATIVE"},
        {"filename": "Pumps_Manual.pdf", "page": 32, "extraction_method": "NATIVE"}
    ]

    model_text = (
        "Based on the manual [Pumps_Manual.pdf | Page 16 | NATIVE], suction pressure must be above 1.5 bar. "
        "Also, bearing clearance specifications are on [Pumps_Manual.pdf | Page 32 | NATIVE]."
    )

    verified, sources_str = reconcile_citations_against_evidence(
        text=model_text,
        retrieved_evidence=evidence
    )

    # Both pages must be present and distinct
    assert len(verified) == 2
    pages = {v["page"] for v in verified}
    assert pages == {16, 32}

    assert "Page 16" in sources_str
    assert "Page 32" in sources_str


def test_xlsx_format_aware_citation():
    """Verify that XLSX spreadsheet chunks retain sheet name and row coordinates in citations."""
    meta = {
        "filename": "Trip_Log.xlsx",
        "sheet_name": "Turbine_Events",
        "row_start": 120,
        "row_end": 145,
        "col_start": "A",
        "col_end": "H",
        "extraction_method": "SPREADSHEET"
    }
    cite = format_grounded_citation(meta)
    assert "[Trip_Log.xlsx | Sheet: Turbine_Events | Rows 120-145 | Cols A:H | SPREADSHEET]" == cite

    # Extraction test
    extracted = extract_and_normalize_citations(text=f"As shown in {cite}")
    assert len(extracted) == 1
    assert extracted[0]["filename"] == "Trip_Log.xlsx"
    assert extracted[0]["sheet_name"] == "Turbine_Events"
    assert extracted[0]["row_start"] == 120
    assert extracted[0]["row_end"] == 145


def test_docx_format_aware_citation():
    """Verify that DOCX section and rendered page citations format and parse properly."""
    meta = {
        "filename": "Operating_Procedure.docx",
        "section_heading": "3.1 Startup Interlocks",
        "page": 4,
        "extraction_method": "DOCUMENT"
    }
    cite = format_grounded_citation(meta)
    assert "[Operating_Procedure.docx | Section: 3.1 Startup Interlocks | Rendered Page 4 | DOCUMENT]" == cite

    extracted = extract_and_normalize_citations(text=f"Refer to {cite}")
    assert len(extracted) == 1
    assert extracted[0]["filename"] == "Operating_Procedure.docx"
    assert extracted[0]["section_heading"] == "3.1 Startup Interlocks"
    assert extracted[0]["page"] == 4


def test_hallucinated_page_snapping_to_nearest():
    """Verify that a model citing Page 15 snaps to retrieved Page 16."""
    evidence = [
        {"filename": "Pumps_Manual.pdf", "page": 16, "extraction_method": "NATIVE"}
    ]
    model_text = "As stated in [Pumps_Manual.pdf | Page 15]"

    verified, sources_str = reconcile_citations_against_evidence(
        text=model_text,
        retrieved_evidence=evidence
    )
    assert len(verified) == 1
    assert verified[0]["page"] == 16
    assert "Page 16" in sources_str
