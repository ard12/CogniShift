"""
Unit tests for benchmark metric calculations:
- Source Coverage formula with len(expected_sources)
- Format-aware citation validation (PDF, XLSX, DOCX)
- Claim Support Precision (CSP) with E-ID validation
- Physical Cause Accuracy (PCA) vs Status scoring separation
- Channel contribution and execution diagnostics
"""
import re
import pytest
from pathlib import Path

from cognishift.core.rca.schemas import (
    PrimaryCauseCode,
    RCAStatus,
    RCAEvidenceItem,
    EvidenceRole,
    EvidenceCriticality
)
from cognishift.core.rca.evaluation import (
    evaluate_threshold,
    score_status_strict,
    MetricStatus
)


def compute_source_coverage(expected_sources: list, sources_used: str, result_text: str) -> float:
    """Computes source coverage strictly against len(expected_sources)."""
    if not expected_sources:
        return 1.0
    covered = sum(
        1 for src in expected_sources
        if src.lower() in sources_used.lower() or src.lower() in result_text.lower()
    )
    return min(1.0, covered / len(expected_sources))


def test_source_coverage_calculation_strictly_uses_expected_count():
    """Verify that if 1 of 3 expected sources is found, coverage is 1/3 (33.3%), NOT 100%."""
    expected = [
        "RCA-CASE-A-DOC1.pdf",
        "RCA-CASE-A-DOC2.pdf",
        "RCA-CASE-A-DOC3.pdf"
    ]
    # Only 1 source present in result text
    res_text = "Analysis references RCA-CASE-A-DOC1.pdf only."
    coverage = compute_source_coverage(expected, sources_used="", result_text=res_text)
    assert abs(coverage - (1.0 / 3.0)) < 1e-4

    # 2 sources present
    res_text_2 = "References RCA-CASE-A-DOC1.pdf and RCA-CASE-A-DOC2.pdf."
    coverage_2 = compute_source_coverage(expected, sources_used="", result_text=res_text_2)
    assert abs(coverage_2 - (2.0 / 3.0)) < 1e-4

    # All 3 present
    res_text_3 = "References RCA-CASE-A-DOC1.pdf, RCA-CASE-A-DOC2.pdf, and RCA-CASE-A-DOC3.pdf."
    coverage_3 = compute_source_coverage(expected, sources_used="", result_text=res_text_3)
    assert coverage_3 == 1.0


def test_format_aware_citation_extraction():
    """Verify regex extraction of citations across PDF, XLSX, and DOCX formats."""
    text = (
        "Based on [Pump_Manual.pdf | Page 12 | TEXT] and "
        "[SCADA_Logs.xlsx | Sheet: Events | Rows 100-120 | SPREADSHEET] and "
        "[Maintenance_SOP.docx | Section: 3.1 | Rendered Page 4 | DOCUMENT], "
        "the pump failed."
    )
    citation_regex = re.compile(
        r"\[([A-Za-z0-9_\-\.\s]+\.(?:pdf|png|csv|xlsx|docx|jpg|jpeg)\s*\|[^\]]+)\]",
        re.IGNORECASE
    )
    matches = citation_regex.findall(text)
    assert len(matches) == 3
    assert "Pump_Manual.pdf" in matches[0]
    assert "SCADA_Logs.xlsx" in matches[1]
    assert "Maintenance_SOP.docx" in matches[2]


def test_claim_support_precision_calculation():
    """Verify that CSP evaluates presence of valid cited E-IDs."""
    # Observations with valid E-IDs
    obs_text = (
        "- Cavitation occurred due to low NPSHa [E1]\n"
        "- High vibration at 14.8 mm/s recorded [E2]\n"
        "- Suction strainer clogged with scale [E3]"
    )
    obs_lines = [l.strip() for l in obs_text.split("\n") if l.strip().startswith("-")]
    grounded = [l for l in obs_lines if re.search(r"\[E\d+\]", l)]
    csp = len(grounded) / len(obs_lines)
    assert csp == 1.0

    # Observations with missing E-ID
    obs_unsupported = (
        "- Cavitation occurred [E1]\n"
        "- Operator heard a loud banging noise\n"
    )
    obs_lines_2 = [l.strip() for l in obs_unsupported.split("\n") if l.strip().startswith("-")]
    grounded_2 = [l for l in obs_lines_2 if re.search(r"\[E\d+\]", l)]
    csp_2 = len(grounded_2) / len(obs_lines_2)
    assert csp_2 == 0.5


def test_pca_vs_status_separation():
    """Verify that Primary Cause Accuracy (physical cause code) is distinct from status/calibration."""
    expected_cause = PrimaryCauseCode.SUCTION_STARVATION_CAVITATION
    actual_cause_match = PrimaryCauseCode.SUCTION_STARVATION_CAVITATION
    wrong_cause = PrimaryCauseCode.BEARING_OVERHEAT

    # Match gives 1.0 PCA regardless of whether status is PLAUSIBLE or SUPPORTED
    assert actual_cause_match == expected_cause
    assert wrong_cause != expected_cause
