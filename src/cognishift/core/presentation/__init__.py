"""
CogniShift Presentation Subsystem.
Provides deterministic, theme-aware, validated PPTX generation with canonical media provenance.
"""
from pathlib import Path
from typing import Optional, List, Dict, Any

from cognishift.core.presentation.schemas import (
    SlideType,
    ThemeName,
    MetricCard,
    SlideSpec,
    PresentationSpec
)
from cognishift.core.presentation.themes import (
    PresentationTheme,
    ThemeColors,
    THEMES,
    get_theme
)
from cognishift.core.presentation.planner import PresentationPlanner
from cognishift.core.presentation.renderer import PresentationRenderer
from cognishift.core.presentation.validator import (
    PresentationValidator,
    PresentationValidationReport
)


def generate_presentation(
    spec: PresentationSpec,
    output_path: Path,
    workspace_id: Optional[int] = None
) -> Path:
    """Convenience helper to render a PresentationSpec to a local file."""
    renderer = PresentationRenderer(workspace_id=workspace_id)
    return renderer.render(spec, output_path)


def validate_presentation(
    file_path: Path,
    expected_slide_count: Optional[int] = None,
    expected_media_shas: Optional[List[str]] = None,
    spec: Optional[Any] = None
) -> PresentationValidationReport:
    """Convenience helper to validate a presentation file."""
    return PresentationValidator.validate_presentation_file(
        file_path=file_path,
        expected_slide_count=expected_slide_count,
        expected_media_shas=expected_media_shas,
        spec=spec
    )


__all__ = [
    "SlideType",
    "ThemeName",
    "MetricCard",
    "SlideSpec",
    "PresentationSpec",
    "PresentationTheme",
    "ThemeColors",
    "THEMES",
    "get_theme",
    "PresentationPlanner",
    "PresentationRenderer",
    "PresentationValidator",
    "PresentationValidationReport",
    "generate_presentation",
    "validate_presentation"
]
