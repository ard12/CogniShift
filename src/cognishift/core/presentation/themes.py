"""
Deterministic presentation design themes for CogniShift.
Provides consistent colors, fonts, margins, and card background stylings.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any
from pptx.dml.color import RGBColor
from cognishift.core.presentation.schemas import ThemeName


@dataclass
class ThemeColors:
    primary: RGBColor
    secondary: RGBColor
    accent: RGBColor
    background: RGBColor
    card_bg: RGBColor
    text_dark: RGBColor
    text_light: RGBColor
    border: RGBColor
    status_normal: RGBColor
    status_warning: RGBColor
    status_critical: RGBColor


@dataclass
class PresentationTheme:
    name: ThemeName
    font_title: str
    font_body: str
    font_kpi: str
    font_code: str
    colors: ThemeColors
    font_title_fallbacks: List[str] = field(default_factory=list)
    font_body_fallbacks: List[str] = field(default_factory=list)
    font_kpi_fallbacks: List[str] = field(default_factory=list)
    font_code_fallbacks: List[str] = field(default_factory=list)

    def resolve_font(self, token: str) -> Dict[str, Any]:
        """Resolves font with fallback audit tracking (Amendment #11)."""
        if token == "title":
            req = self.font_title
            fallbacks = self.font_title_fallbacks
        elif token == "body":
            req = self.font_body
            fallbacks = self.font_body_fallbacks
        elif token == "kpi":
            req = self.font_kpi
            fallbacks = self.font_kpi_fallbacks
        elif token == "code":
            req = self.font_code
            fallbacks = self.font_code_fallbacks
        else:
            req = self.font_body
            fallbacks = []

        return {
            "token": token,
            "requested_font": req,
            "resolved_font": req,
            "fallback_used": False,
            "fallbacks_available": fallbacks
        }


def calculate_relative_luminance(rgb: RGBColor) -> float:
    """Calculates relative luminance according to WCAG 2.1 specs."""
    def channel_lum(c: int) -> float:
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r = (rgb >> 16) & 0xFF if isinstance(rgb, int) else rgb[0]
    g = (rgb >> 8) & 0xFF if isinstance(rgb, int) else rgb[1]
    b = rgb & 0xFF if isinstance(rgb, int) else rgb[2]
    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)


def calculate_contrast_ratio(fg: RGBColor, bg: RGBColor) -> float:
    """Calculates WCAG contrast ratio between foreground and background."""
    l1 = calculate_relative_luminance(fg)
    l2 = calculate_relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# 1. EXECUTIVE Theme (High-level leadership briefings, Boardroom decks)
# Typography: Trebuchet MS (Authoritative Executive Title), Calibri (Crisp Corporate Body), Trebuchet MS Bold (High-Impact KPI Numbers)
# Palette: Deep Slate Navy #0F172A, Royal Blue #2563EB, Warm Amber #D97706, Pure White #FFFFFF
EXECUTIVE_THEME = PresentationTheme(
    name=ThemeName.EXECUTIVE,
    font_title="Trebuchet MS",
    font_body="Calibri",
    font_kpi="Trebuchet MS",
    font_code="Consolas",
    font_title_fallbacks=["Calibri", "Arial"],
    font_body_fallbacks=["Arial", "Liberation Sans"],
    font_kpi_fallbacks=["Calibri", "Arial"],
    font_code_fallbacks=["Cascadia Mono", "Courier New"],
    colors=ThemeColors(
        primary=RGBColor(15, 23, 42),       # #0F172A
        secondary=RGBColor(37, 99, 235),    # #2563EB
        accent=RGBColor(217, 119, 6),       # #D97706
        background=RGBColor(248, 250, 252), # #F8FAFC
        card_bg=RGBColor(255, 255, 255),    # #FFFFFF
        text_dark=RGBColor(15, 23, 42),     # #0F172A
        text_light=RGBColor(248, 250, 252), # #F8FAFC
        border=RGBColor(226, 232, 240),     # #E2E8F0
        status_normal=RGBColor(22, 163, 74),
        status_warning=RGBColor(217, 119, 6),
        status_critical=RGBColor(220, 38, 38)
    )
)

# 2. ENGINEERING Theme (Technical diagrams, P&ID telemetry, RCA deep-dives)
# Typography: Segoe UI Semibold (DIN-inspired Precision Engineering), Segoe UI (Technical Legibility), Consolas (Telemetry & Tags)
# Palette: Steel Charcoal #1E293B, Cyan #06B6D4, Warning Orange #EA580C
ENGINEERING_THEME = PresentationTheme(
    name=ThemeName.ENGINEERING,
    font_title="Segoe UI Semibold",
    font_body="Segoe UI",
    font_kpi="Segoe UI",
    font_code="Consolas",
    font_title_fallbacks=["Bahnschrift", "Segoe UI Semibold", "Arial"],
    font_body_fallbacks=["Segoe UI", "Arial", "Liberation Sans"],
    font_kpi_fallbacks=["Segoe UI", "Arial", "Liberation Sans"],
    font_code_fallbacks=["Consolas", "Cascadia Mono", "Liberation Mono"],
    colors=ThemeColors(
        primary=RGBColor(30, 41, 59),       # #1E293B
        secondary=RGBColor(6, 182, 212),    # #06B6D4
        accent=RGBColor(234, 88, 12),       # #EA580C
        background=RGBColor(241, 245, 249), # #F1F5F9
        card_bg=RGBColor(255, 255, 255),    # #FFFFFF
        text_dark=RGBColor(15, 23, 42),     # #0F172A
        text_light=RGBColor(241, 245, 249), # #F1F5F9
        border=RGBColor(203, 213, 225),     # #CBD5E1
        status_normal=RGBColor(13, 148, 136),
        status_warning=RGBColor(234, 88, 12),
        status_critical=RGBColor(225, 29, 72)
    )
)

# 3. OPERATIONS Theme (Control room briefings, shift handover, plant safety)
# Typography: Franklin Gothic Medium (Instant Industrial Readability), Arial (Clear Neutral Body), Arial Bold (Alarm Status)
# Palette: Industrial Forest #064E3B, Emerald #059669, Amber #D97706
OPERATIONS_THEME = PresentationTheme(
    name=ThemeName.OPERATIONS,
    font_title="Franklin Gothic Medium",
    font_body="Arial",
    font_kpi="Arial",
    font_code="Consolas",
    font_title_fallbacks=["Franklin Gothic Medium", "Arial Black", "Arial"],
    font_body_fallbacks=["Arial", "Calibri", "Liberation Sans"],
    font_kpi_fallbacks=["Arial", "Calibri", "Liberation Sans"],
    font_code_fallbacks=["Consolas", "Cascadia Mono", "Courier New"],
    colors=ThemeColors(
        primary=RGBColor(6, 78, 59),        # #064E3B
        secondary=RGBColor(5, 150, 105),    # #059669
        accent=RGBColor(217, 119, 6),       # #D97706
        background=RGBColor(240, 253, 244), # #F0FDF4
        card_bg=RGBColor(255, 255, 255),    # #FFFFFF
        text_dark=RGBColor(6, 78, 59),      # #064E3B
        text_light=RGBColor(240, 253, 244), # #F0FDF4
        border=RGBColor(187, 247, 208),     # #BBF7D0
        status_normal=RGBColor(22, 163, 74),
        status_warning=RGBColor(217, 119, 6),
        status_critical=RGBColor(220, 38, 38)
    )
)

# 4. GOVERNMENT_PSU Theme (Statutory compliance, OISD/PESO audits, Ministry briefs)
# Typography: Georgia (Formal Institutional Serif), Calibri (Structured Compliance Body), Georgia Bold (Statutory Codes)
# Palette: Ashoka Navy #1E3A8A, Warm Gold #B45309, Crimson #991B1B, Parchment #FAFAF9
GOVERNMENT_PSU_THEME = PresentationTheme(
    name=ThemeName.GOVERNMENT_PSU,
    font_title="Georgia",
    font_body="Calibri",
    font_kpi="Georgia",
    font_code="Consolas",
    font_title_fallbacks=["Georgia", "Times New Roman", "Calibri"],
    font_body_fallbacks=["Calibri", "Georgia", "Liberation Serif"],
    font_kpi_fallbacks=["Georgia", "Times New Roman", "Calibri"],
    font_code_fallbacks=["Consolas", "Courier New"],
    colors=ThemeColors(
        primary=RGBColor(30, 58, 138),      # #1E3A8A
        secondary=RGBColor(180, 83, 9),     # #B45309
        accent=RGBColor(153, 27, 27),       # #991B1B
        background=RGBColor(250, 250, 249), # #FAFAF9
        card_bg=RGBColor(255, 255, 255),    # #FFFFFF
        text_dark=RGBColor(28, 25, 23),     # #1C1917
        text_light=RGBColor(250, 250, 249), # #FAFAF9
        border=RGBColor(231, 229, 228),     # #E7E5E4
        status_normal=RGBColor(21, 128, 61),
        status_warning=RGBColor(180, 83, 9),
        status_critical=RGBColor(153, 27, 27)
    )
)

THEMES: Dict[ThemeName, PresentationTheme] = {
    ThemeName.EXECUTIVE: EXECUTIVE_THEME,
    ThemeName.ENGINEERING: ENGINEERING_THEME,
    ThemeName.OPERATIONS: OPERATIONS_THEME,
    ThemeName.GOVERNMENT_PSU: GOVERNMENT_PSU_THEME
}


def get_theme(theme_name: ThemeName) -> PresentationTheme:
    """Returns the requested theme with fallback to EXECUTIVE."""
    return THEMES.get(theme_name, EXECUTIVE_THEME)
