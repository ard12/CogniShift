"""
Comprehensive test suite for CogniShift Presentation Generation and Canonical Provenance:
- 4 Deterministic themes rendering (EXECUTIVE, ENGINEERING, OPERATIONS, GOVERNMENT_PSU)
- Canonical PNG artifact embedding with exact SHA-256 byte matching in ppt/media/*
- Pagination over shrinking policy enforcement
- Structural OpenXML package validation
- Round-trip generation, validation, and re-ingestion
"""
import hashlib
import io
import zipfile
from typing import Tuple, List, Dict, Any, Optional
import pytest
from pathlib import Path
from PIL import Image

from cognishift.core.presentation import (
    SlideType,
    ThemeName,
    MetricCard,
    SlideSpec,
    PresentationSpec,
    PresentationPlanner,
    PresentationRenderer,
    PresentationValidator,
    generate_presentation,
    validate_presentation
)
from cognishift.core.document_processing.office_renderer import extract_pptx_structured_content


@pytest.fixture
def sample_canonical_chart(tmp_path: Path) -> Tuple[Path, str]:
    """Creates a sample canonical PNG chart image and returns (path, sha256)."""
    img_path = tmp_path / "pressure_trend_canonical.png"
    # Create distinct 400x300 image
    im = Image.new("RGB", (400, 300), color=(25, 80, 150))
    im.save(str(img_path), "PNG")
    img_bytes = img_path.read_bytes()
    sha256 = hashlib.sha256(img_bytes).hexdigest()
    return img_path, sha256


def test_presentation_themes_rendering(tmp_path: Path):
    """Verify all 4 deterministic themes render valid 16:9 presentations."""
    themes = [
        ThemeName.EXECUTIVE,
        ThemeName.ENGINEERING,
        ThemeName.OPERATIONS,
        ThemeName.GOVERNMENT_PSU
    ]

    for theme in themes:
        spec = PresentationSpec(
            title=f"Incident Brief — {theme.value.upper()}",
            subtitle="Automated Root Cause Diagnosis",
            theme=theme,
            slides=[
                SlideSpec(
                    slide_type=SlideType.TITLE,
                    title=f"Incident Brief — {theme.value.upper()}",
                    subtitle="System Trip Diagnostics"
                ),
                SlideSpec(
                    slide_type=SlideType.METRIC_KPI,
                    title="Key Operating Metrics",
                    metrics=[
                        MetricCard(label="Pressure PT-101", value="46.8 barg", status="CRITICAL"),
                        MetricCard(label="Temp TT-201", value="205 degC", status="NORMAL")
                    ]
                ),
                SlideSpec(
                    slide_type=SlideType.SOURCE_APPENDIX,
                    title="Auditable Citations",
                    bullets=["DCS Telemetry Log [Page 1]", "P&ID 001-A-102 [Sheet 1]"]
                )
            ]
        )

        out_path = tmp_path / f"deck_{theme.value}.pptx"
        generate_presentation(spec, out_path)

        report = validate_presentation(out_path, expected_slide_count=3)
        assert report.valid is True
        assert report.slide_count == 3
        assert report.file_size > 5000
        assert report.error_message is None


def test_canonical_artifact_sha256_provenance(tmp_path: Path, sample_canonical_chart, monkeypatch):
    """
    Verify that an embedded canonical artifact matches byte-for-byte in ppt/media/*,
    verifying zero synthetic image fabrication or lossy distortion.
    """
    chart_path, chart_sha256 = sample_canonical_chart

    # Mock _resolve_artifact_image to return the canonical chart path
    renderer = PresentationRenderer(workspace_id=99)
    monkeypatch.setattr(renderer, "_resolve_artifact_image", lambda art_id, **_kwargs: chart_path)

    spec = PresentationSpec(
        title="Telemetry Investigation with Canonical Chart",
        theme=ThemeName.ENGINEERING,
        slides=[
            SlideSpec(
                slide_type=SlideType.TITLE,
                title="Investigation Brief"
            ),
            SlideSpec(
                slide_type=SlideType.CHART,
                title="Pressure Excursion Timeline",
                subtitle="High-frequency historian telemetry",
                chart_artifact_ids=[101],
                bullets=["Excursion initiated at 08:14:02 UTC.", "Interlock tripped vessel V-101."]
            )
        ]
    )

    out_path = tmp_path / "provenance_deck.pptx"
    renderer.render(spec, out_path)

    # Validate OpenXML and exact SHA-256 byte presence in ppt/media/*
    report = validate_presentation(
        file_path=out_path,
        expected_slide_count=2,
        expected_media_shas=[chart_sha256]
    )

    assert report.valid is True
    assert report.slide_count == 2
    assert report.media_files_verified >= 1
    assert chart_sha256 in report.matched_media_shas
    assert len(report.unmatched_media_shas) == 0


def test_investigation_deck_embeds_grounded_visuals_on_slides_5_and_6(
    tmp_path: Path, sample_canonical_chart, monkeypatch
):
    """The canonical RCA deck must contain actual image relationships on Slides 5 and 6."""
    chart_path, chart_sha256 = sample_canonical_chart
    pid_path = tmp_path / "plant_pid_page_1.png"
    Image.new("RGB", (800, 500), color=(240, 245, 250)).save(pid_path, "PNG")
    pid_sha256 = hashlib.sha256(pid_path.read_bytes()).hexdigest()

    renderer = PresentationRenderer(workspace_id=99)
    resolved = {101: chart_path, 201: pid_path}
    monkeypatch.setattr(
        renderer,
        "_resolve_artifact_image",
        lambda art_id, **_kwargs: resolved.get(art_id),
    )

    spec = PresentationPlanner.plan_investigation_deck(
        title="Incident Investigation & Root Cause Analysis",
        subtitle="Unit 100 Pressure Excursion Review",
        goal="Investigate the V-101 pressure excursion",
        topology_image_artifact_ids=[201],
        topology_right=["Equipment: V-101", "Primary safeguard: XV-101"],
        chart_artifact_ids=[101],
        chart_takeaways=["PT-101 crossed the 45.0 barg design threshold."],
    )
    out_path = tmp_path / "Management_RCA_Brief.pptx"
    renderer.render(spec, out_path)

    report = validate_presentation(
        out_path,
        expected_slide_count=10,
        expected_media_shas=[pid_sha256, chart_sha256],
        spec=spec,
    )
    assert report.valid is True
    assert set(report.matched_media_shas) == {pid_sha256, chart_sha256}

    with zipfile.ZipFile(out_path) as archive:
        for slide_number in (5, 6):
            slide_xml = archive.read(f"ppt/slides/slide{slide_number}.xml")
            rels_xml = archive.read(f"ppt/slides/_rels/slide{slide_number}.xml.rels")
            assert b"<p:pic>" in slide_xml
            assert b"/relationships/image" in rels_xml


def test_pagination_over_shrinking():
    """Verify that excessive bullets and rows trigger pagination instead of font shrinking."""
    many_recs = [
        f"Recommendation #{i}: Inspect subsystem {i} for corrosion and integrity."
        for i in range(1, 12)  # 11 recommendations
    ]

    spec = PresentationPlanner.plan_presentation(
        title="Long Diagnostic Plan",
        goal="Review boiler overhaul steps",
        evidence_snippets=["Step 1", "Step 2"],
        source_citations=["Manual 1 | Page 4"],
        recommendations=many_recs
    )

    # With 11 recs and max 5 per slide, should produce multiple CAPA slides
    capa_slides = [s for s in spec.slides if s.slide_type == SlideType.RECOMMENDED_ACTIONS]
    assert len(capa_slides) >= 2
    for s in capa_slides:
        assert len(s.bullets) <= 5


def test_round_trip_reingestion(tmp_path: Path):
    """
    Round-trip acceptance test:
    Generates a PPTX presentation, validates it, and re-ingests it via extract_pptx_structured_content.
    Verifies that CogniShift can query and retrieve its own generated presentations!
    """
    spec = PresentationSpec(
        title="Management Root Cause Analysis Brief",
        subtitle="Vessel V-101 Overpressure Incident",
        theme=ThemeName.EXECUTIVE,
        slides=[
            SlideSpec(
                slide_type=SlideType.TITLE,
                title="Management Root Cause Analysis Brief",
                subtitle="Vessel V-101 Overpressure Incident"
            ),
            SlideSpec(
                slide_type=SlideType.EXECUTIVE_SUMMARY,
                title="Executive Incident Summary",
                bullets=[
                    "Primary root cause: Nitrogen regulator PCV-102 diaphragm failed open.",
                    "Secondary factor: Manual bypass valve HV-102 was cracked 15% open.",
                    "Peak excursion pressure reached 46.8 barg before PSH-101 interlock trip."
                ],
                speaker_notes="Key finding: Nitrogen overpressure coupled with manual valve leakage."
            ),
            SlideSpec(
                slide_type=SlideType.RECOMMENDED_ACTIONS,
                title="Corrective Actions",
                bullets=[
                    "Replace diaphragm on PCV-102 with reinforced fluorocarbon elastomer.",
                    "Install tamper-evident car-seal on bypass valve HV-102.",
                    "Update SOP-402 with mandatory dual-supervisor signoff."
                ]
            ),
            SlideSpec(
                slide_type=SlideType.SOURCE_APPENDIX,
                title="Source Appendix",
                bullets=[
                    "Operating Manual V-101 | Section: Pressure Control | TEXT",
                    "DCS Historian Log | Rows 100-250 | SPREADSHEET",
                    "P&ID Diagram 001-A-102 | Page 1 | VISUAL"
                ]
            )
        ]
    )

    out_path = tmp_path / "Management_RCA_Brief.pptx"
    generate_presentation(spec, out_path)

    # 1. Validate structure
    report = validate_presentation(out_path, expected_slide_count=4)
    assert report.valid is True
    assert report.slide_count == 4

    # 2. Re-ingest presentation
    reingested_slides = extract_pptx_structured_content(out_path)
    assert len(reingested_slides) == 4

    # Verify slide 2 content
    slide2 = reingested_slides[1]
    assert slide2["slide_number"] == 2
    assert "PCV-102 diaphragm failed open" in slide2["text"]
    assert "46.8 barg" in slide2["text"]
    assert slide2["has_notes"] is True
    assert "Nitrogen overpressure coupled with manual valve leakage" in slide2["text"]

    # Verify slide 3 content
    slide3 = reingested_slides[2]
    assert slide3["slide_number"] == 3
    assert "Corrective Actions" in slide3["slide_title"]
    assert "tamper-evident car-seal" in slide3["text"]
