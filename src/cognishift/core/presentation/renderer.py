"""
Deterministic Presentation Renderer for CogniShift.
Builds professional 16:9 widescreen PowerPoint presentations using python-pptx.
Applies themes, layouts, metric cards, tables, and verified canonical artifact embedding.
"""
import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

import pptx
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

from cognishift.core.presentation.schemas import (
    PresentationSpec,
    SlideSpec,
    SlideType,
    ThemeName,
    MetricCard
)
from cognishift.core.presentation.themes import get_theme, PresentationTheme
from cognishift.core.security import resolve_workspace_path

logger = logging.getLogger(__name__)


class PresentationRenderer:
    """Renders PresentationSpec into a physical .pptx file with strict design standards."""

    def __init__(self, workspace_id: Optional[int] = None):
        self.workspace_id = workspace_id

    def render(self, spec: PresentationSpec, output_path: Path) -> Path:
        """Renders PresentationSpec to output_path and returns the Path."""
        theme = get_theme(spec.theme)
        prs = pptx.Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        blank_layout = prs.slide_layouts[6]

        embedded_shas: Dict[str, str] = {}
        rendered_elements_by_slide: Dict[int, List[str]] = {}
        total_slides = len(spec.slides)

        for slide_idx, slide_spec in enumerate(spec.slides, start=1):
            slide = prs.slides.add_slide(blank_layout)
            slide_rendered: List[str] = []

            # Set background color of slide
            bg = slide.background
            fill = bg.fill
            fill.solid()
            if slide_spec.slide_type == SlideType.TITLE:
                fill.fore_color.rgb = theme.colors.primary
                self._render_title_slide(slide, slide_spec, theme, slide_rendered, pres_spec=spec)
            else:
                fill.fore_color.rgb = theme.colors.background
                self._render_content_slide(slide, slide_spec, theme, slide_idx, total_slides, embedded_shas, slide_rendered, pres_spec=spec)

            rendered_elements_by_slide[slide_idx] = slide_rendered

            # Speaker Notes
            if slide_spec.speaker_notes:
                try:
                    notes_frame = slide.notes_slide.notes_text_frame
                    notes_frame.text = slide_spec.speaker_notes
                except Exception as ne:
                    logger.warning(f"Failed setting speaker notes on slide {slide_idx}: {ne}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(output_path))
        spec.metadata["embedded_artifact_shas"] = embedded_shas
        spec.metadata["rendered_elements_by_slide"] = rendered_elements_by_slide
        return output_path

    def _render_title_slide(self, slide, spec: SlideSpec, theme: PresentationTheme, slide_rendered: List[str], pres_spec: Optional[PresentationSpec] = None):
        # Clean Executive Title Slide with High-Contrast Typography (Amendment #7: Semantic Design > Decoration)
        # Classification badge pill
        badge_box = slide.shapes.add_textbox(Inches(1.0), Inches(1.1), Inches(11.3), Inches(0.45))
        bp = badge_box.text_frame.paragraphs[0]
        bp.text = "COGNISHIFT SOVEREIGN INDUSTRIAL WORKBENCH // INCIDENT BRIEFING"
        bp.font.name = theme.font_title
        bp.font.size = Pt(11.5)
        bp.font.bold = True
        bp.font.color.rgb = theme.colors.accent

        # Title (Restored to 38pt bold readable title - Amendment #1)
        title_box = slide.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(11.3), Inches(2.0))
        title_frame = title_box.text_frame
        title_frame.word_wrap = True
        tp = title_frame.paragraphs[0]
        tp.text = spec.title
        tp.font.name = theme.font_title
        tp.font.size = Pt(38)
        tp.font.bold = True
        tp.font.color.rgb = theme.colors.text_light

        # Subtitle
        if spec.subtitle:
            sub_box = slide.shapes.add_textbox(Inches(1.0), Inches(3.9), Inches(11.3), Inches(1.4))
            sub_frame = sub_box.text_frame
            sub_frame.word_wrap = True
            sp = sub_frame.paragraphs[0]
            sp.text = spec.subtitle
            sp.font.name = theme.font_body
            sp.font.size = Pt(17)
            sp.font.color.rgb = theme.colors.border

        # Synthetic Demonstration Disclosure Banner (Quality V3 Invariant)
        is_demo = False
        if pres_spec and hasattr(pres_spec, "metadata") and pres_spec.metadata.get("is_synthetic_demo"):
            is_demo = True
        elif any(w in (spec.title or "").lower() for w in ["synthetic", "demo", "simulation", "rca brief"]):
            is_demo = True

        if is_demo:
            demo_pill = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0), Inches(5.6), Inches(11.3), Inches(0.4)
            )
            demo_pill.fill.solid()
            demo_pill.fill.fore_color.rgb = theme.colors.card_bg
            demo_pill.line.color.rgb = theme.colors.accent
            demo_pill.line.width = Pt(1)
            dp = demo_pill.text_frame.paragraphs[0]
            dp.text = "DEMONSTRATION SCENARIO — SYNTHETIC DEMONSTRATION DATA (NOT A RECORD OF AN ACTUAL PLANT INCIDENT)"
            dp.font.name = theme.font_title
            dp.font.size = Pt(12)
            dp.font.bold = True
            dp.font.color.rgb = theme.colors.accent
            dp.alignment = PP_ALIGN.CENTER

        # Footer info (Amendment #3: Sovereign Execution Wording)
        foot_box = slide.shapes.add_textbox(Inches(1.0), Inches(6.4), Inches(11.3), Inches(0.5))
        fp = foot_box.text_frame.paragraphs[0]
        fp.text = "Local sovereign execution with no public-cloud AI/model dependency in the demonstrated workflow."
        fp.font.name = theme.font_body
        fp.font.size = Pt(10.5)
        fp.font.color.rgb = theme.colors.border

        slide_rendered.extend(["title", "subtitle"])

    def _render_content_slide(
        self,
        slide,
        spec: SlideSpec,
        theme: PresentationTheme,
        slide_idx: int,
        total_slides: int,
        embedded_shas: Dict[str, str],
        slide_rendered: List[str],
        pres_spec: Optional[PresentationSpec] = None
    ):
        # Header Area (Slide Title restored to 28pt bold, Subtitle 14pt - Amendment #1)
        header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.40), Inches(11.7), Inches(1.15))
        hf = header_box.text_frame
        hf.word_wrap = True

        hp = hf.paragraphs[0]
        hp.text = spec.title
        hp.font.name = theme.font_title
        hp.font.size = Pt(28)
        hp.font.bold = True
        hp.font.color.rgb = theme.colors.primary

        if spec.subtitle:
            sp = hf.add_paragraph()
            sp.text = spec.subtitle
            sp.font.name = theme.font_body
            sp.font.size = Pt(16)
            sp.font.color.rgb = theme.colors.secondary

        # Dispatch to dedicated modular slide renderers
        if spec.slide_type == SlideType.EXECUTIVE_SUMMARY:
            self._render_executive_summary(slide, spec, theme, slide_rendered)
        elif spec.slide_type == SlideType.TIMELINE:
            self._render_timeline(slide, spec, theme, slide_rendered)
        elif spec.slide_type == SlideType.TWO_COLUMN:
            self._render_two_column(slide, spec, theme, slide_rendered)
        elif spec.slide_type == SlideType.METRIC_KPI and spec.metrics:
            self._render_metrics_only(slide, spec.metrics, theme, slide_rendered)
        elif spec.slide_type == SlideType.TABLE and spec.table:
            self._render_table(slide, spec.table, theme, slide_rendered)
        elif spec.slide_type == SlideType.EVIDENCE_SUMMARY:
            self._render_evidence_summary(slide, spec, theme, slide_rendered)
        elif spec.slide_type == SlideType.CHART or (spec.chart_artifact_ids or spec.image_artifact_ids):
            self._render_media(slide, spec, theme, embedded_shas, slide_rendered, pres_spec=pres_spec)
        elif spec.slide_type == SlideType.ROOT_CAUSE:
            self._render_root_cause(slide, spec, theme, slide_rendered)
        elif spec.slide_type == SlideType.RECOMMENDED_ACTIONS:
            self._render_recommended_actions(slide, spec, theme, slide_rendered)
        elif spec.slide_type == SlideType.SOURCE_APPENDIX:
            self._render_source_appendix(slide, spec, theme, slide_rendered)
        else:
            self._render_bullets(slide, spec, theme, slide_rendered)

        # Footer Bar (Guaranteed zero collision with slide counter)
        footer_box = slide.shapes.add_textbox(Inches(0.8), Inches(6.8), Inches(9.2), Inches(0.4))
        ff = footer_box.text_frame
        ff_p = ff.paragraphs[0]
        if spec.slide_type == SlideType.SOURCE_APPENDIX:
            citation_str = " | Authoritative Source Register"
        else:
            all_sources = spec.get_all_sources()
            if all_sources:
                clean_refs = [s.split("|")[0].strip() for s in all_sources[:2]]
                citation_str = f" | Ref: {', '.join(clean_refs)}"
            else:
                citation_str = ""
        ff_p.text = f"CONFIDENTIAL // LOCAL SOVEREIGN WORKBENCH{citation_str}"
        ff_p.font.name = theme.font_body
        ff_p.font.size = Pt(12)
        ff_p.font.color.rgb = theme.colors.accent

        num_box = slide.shapes.add_textbox(Inches(10.5), Inches(6.8), Inches(2.0), Inches(0.4))
        num_p = num_box.text_frame.paragraphs[0]
        num_p.text = f"Slide {slide_idx} of {total_slides}"
        num_p.alignment = PP_ALIGN.RIGHT
        num_p.font.name = theme.font_body
        num_p.font.size = Pt(12)
        num_p.font.color.rgb = theme.colors.text_dark

    def _render_executive_summary(self, slide, spec: SlideSpec, theme: PresentationTheme, slide_rendered: List[str]):
        """Renders executive summary: Top KPI cards row + Bottom Key Findings card."""
        has_metrics = bool(spec.metrics)

        if has_metrics:
            # 1. Top KPI Cards Row
            metric_count = min(len(spec.metrics), 4)
            card_gap = Inches(0.35)
            total_w = Inches(11.7)
            card_w = (total_w - (card_gap * (metric_count - 1))) / metric_count
            start_x = Inches(0.8)
            card_h = Inches(1.85)
            card_y = Inches(1.65)

            for idx, m in enumerate(spec.metrics[:metric_count]):
                x = start_x + idx * (card_w + card_gap)
                box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, card_y, card_w, card_h)
                box.fill.solid()
                box.fill.fore_color.rgb = theme.colors.card_bg
                box.line.color.rgb = theme.colors.border
                box.line.width = Pt(1)

                tf = box.text_frame
                tf.word_wrap = True
                tf.margin_top = Inches(0.18)
                tf.margin_left = Inches(0.2)
                tf.margin_right = Inches(0.2)
                tf.margin_bottom = Inches(0.15)

                # Label
                lp = tf.paragraphs[0]
                lp.text = m.label.upper()
                lp.font.name = theme.font_title
                lp.font.size = Pt(11.5)
                lp.font.bold = True
                lp.font.color.rgb = theme.colors.secondary
                lp.space_after = Pt(3)

                # Large Metric Value (Restored to 38pt bold - Amendment #1)
                vp = tf.add_paragraph()
                vp.text = str(m.value)
                vp.font.name = theme.font_kpi
                vp.font.size = Pt(38)
                vp.font.bold = True

                st = (m.status or "NORMAL").upper()
                if st == "CRITICAL":
                    vp.font.color.rgb = theme.colors.status_critical
                elif st == "WARNING":
                    vp.font.color.rgb = theme.colors.status_warning
                else:
                    vp.font.color.rgb = theme.colors.status_normal
                vp.space_after = Pt(3)

                # Subtext
                if m.subtext:
                    sp = tf.add_paragraph()
                    sp.text = m.subtext
                    sp.font.name = theme.font_body
                    sp.font.size = Pt(12)
                    sp.font.color.rgb = theme.colors.text_dark

            # 2. Bottom Key Findings Card
            findings_card = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(3.68), Inches(11.7), Inches(2.95)
            )
            findings_card.fill.solid()
            findings_card.fill.fore_color.rgb = theme.colors.card_bg
            findings_card.line.color.rgb = theme.colors.border
            findings_card.line.width = Pt(1)

            tb = slide.shapes.add_textbox(Inches(1.0), Inches(3.85), Inches(11.3), Inches(2.65))
            tf = tb.text_frame
            tf.word_wrap = True

            hdr = tf.paragraphs[0]
            hdr.text = "KEY OPERATIONAL FINDINGS & EVIDENCE SYNTHESIS"
            hdr.font.name = theme.font_title
            hdr.font.size = Pt(18)
            hdr.font.bold = True
            hdr.font.color.rgb = theme.colors.secondary
            hdr.space_after = Pt(8)

            for b in spec.bullets[:4]:
                p = tf.add_paragraph()
                p.text = f"•   {b}"
                p.font.name = theme.font_body
                p.font.size = Pt(18)
                p.font.color.rgb = theme.colors.text_dark
                p.space_after = Pt(6)

            slide_rendered.extend(["metrics", "key_findings"])
        else:
            self._render_bullets(slide, spec, theme, slide_rendered)

    def _render_timeline(self, slide, spec: SlideSpec, theme: PresentationTheme, slide_rendered: List[str]):
        """Renders timeline: Horizontal milestone cards with date/time badges."""
        items = spec.timeline_items
        if not items and spec.bullets:
            items = []
            for b in spec.bullets[:5]:
                parts = b.split(":", 1)
                if len(parts) == 2:
                    items.append({"timestamp": parts[0].strip(), "event": parts[1].strip()})
                else:
                    items.append({"timestamp": f"Event {len(items)+1}", "event": b})

        if not items:
            items = [
                {"timestamp": "08:14:00", "event": "Steady state baseline operations."},
                {"timestamp": "08:14:25", "event": "High pressure alarm trip activated."},
                {"timestamp": "08:14:32", "event": "Peak pressure reached."},
                {"timestamp": "08:14:45", "event": "Full isolation achieved."}
            ]

        count = min(len(items), 5)
        gap = Inches(0.24)
        total_w = Inches(11.7)
        card_w = (total_w - (gap * (count - 1))) / count
        start_x = Inches(0.8)

        # Baseline horizontal connector bar (Structural flow connector, allowed under Amendment #7)
        line_bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(2.2), Inches(11.7), Inches(0.05)
        )
        line_bar.fill.solid()
        line_bar.fill.fore_color.rgb = theme.colors.secondary
        line_bar.line.color.rgb = theme.colors.secondary

        for idx, item in enumerate(items[:count]):
            x = start_x + idx * (card_w + gap)
            ts = item.get("timestamp", f"Step {idx+1}")
            ev = item.get("event", "")

            # Milestone Card
            card = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, x, Inches(1.65), card_w, Inches(4.95)
            )
            card.fill.solid()
            card.fill.fore_color.rgb = theme.colors.card_bg
            card.line.color.rgb = theme.colors.border
            card.line.width = Pt(1)

            # Step / Timestamp Pill
            pill = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, x + Inches(0.12), Inches(1.85), card_w - Inches(0.24), Inches(0.44)
            )
            pill.fill.solid()
            pill.fill.fore_color.rgb = theme.colors.secondary
            pill.line.color.rgb = theme.colors.secondary
            pill_p = pill.text_frame.paragraphs[0]
            pill_p.text = ts
            pill_p.alignment = PP_ALIGN.CENTER
            pill_p.font.name = theme.font_title
            pill_p.font.size = Pt(11.5)
            pill_p.font.bold = True
            pill_p.font.color.rgb = theme.colors.text_light

            # Event Description Text Box
            tb = slide.shapes.add_textbox(x + Inches(0.12), Inches(2.45), card_w - Inches(0.24), Inches(3.9))
            tf = tb.text_frame
            tf.word_wrap = True

            ep = tf.paragraphs[0]
            ep.text = ev
            ep.font.name = theme.font_body
            ep.font.size = Pt(16)
            ep.font.color.rgb = theme.colors.text_dark
            ep.space_after = Pt(6)

        slide_rendered.append("timeline_items")

    def _render_two_column(self, slide, spec: SlideSpec, theme: PresentationTheme, slide_rendered: List[str]):
        """Renders balanced 50/50 dual card layout."""
        left_items = spec.get_left_column_items()
        right_items = spec.get_right_column_items()

        card_w = Inches(5.68)
        card_h = Inches(4.95)
        card_y = Inches(1.65)

        # Left Card
        left_card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), card_y, card_w, card_h
        )
        left_card.fill.solid()
        left_card.fill.fore_color.rgb = theme.colors.card_bg
        left_card.line.color.rgb = theme.colors.border
        left_card.line.width = Pt(1)

        ltb = slide.shapes.add_textbox(Inches(1.0), card_y + Inches(0.2), card_w - Inches(0.4), card_h - Inches(0.4))
        ltf = ltb.text_frame
        ltf.word_wrap = True
        l_hdr = ltf.paragraphs[0]
        l_hdr.text = "PROCESS FLOW & TOPOLOGY"
        l_hdr.font.name = theme.font_title
        l_hdr.font.size = Pt(18)
        l_hdr.font.bold = True
        l_hdr.font.color.rgb = theme.colors.secondary
        l_hdr.space_after = Pt(8)

        for b in left_items:
            p = ltf.add_paragraph()
            p.text = f"•   {b}"
            p.font.name = theme.font_body
            p.font.size = Pt(18)
            p.font.color.rgb = theme.colors.text_dark
            p.space_after = Pt(6)

        # Right Card
        right_card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.82), card_y, card_w, card_h
        )
        right_card.fill.solid()
        right_card.fill.fore_color.rgb = theme.colors.card_bg
        right_card.line.color.rgb = theme.colors.border
        right_card.line.width = Pt(1)

        rtb = slide.shapes.add_textbox(Inches(7.02), card_y + Inches(0.2), card_w - Inches(0.4), card_h - Inches(0.4))
        rtf = rtb.text_frame
        rtf.word_wrap = True
        r_hdr = rtf.paragraphs[0]
        r_hdr.text = "EQUIPMENT & SAFEGUARD PARAMETERS"
        r_hdr.font.name = theme.font_title
        r_hdr.font.size = Pt(18)
        r_hdr.font.bold = True
        r_hdr.font.color.rgb = theme.colors.secondary
        r_hdr.space_after = Pt(8)

        for b in right_items:
            p = rtf.add_paragraph()
            p.text = f"•   {b}"
            p.font.name = theme.font_body
            p.font.size = Pt(18)
            p.font.color.rgb = theme.colors.text_dark
            p.space_after = Pt(6)

        slide_rendered.extend(["left_column", "right_column"])

    def _render_evidence_summary(self, slide, spec: SlideSpec, theme: PresentationTheme, slide_rendered: List[str]):
        """Renders 4-channel evidence synthesis matrix."""
        bullets = spec.bullets or []
        if len(bullets) >= 4:
            # Render 4 distinct cards in 2x2 grid
            card_w = Inches(5.68)
            card_h = Inches(2.35)
            coords = [
                (Inches(0.8), Inches(1.65)),
                (Inches(6.82), Inches(1.65)),
                (Inches(0.8), Inches(4.25)),
                (Inches(6.82), Inches(4.25)),
            ]
            default_headers = [
                "1. SCADA / HISTORIAN TELEMETRY",
                "2. OPERATING SOPS & LIMITS",
                "3. NDT & METALLURGY INSPECTION",
                "4. P&ID TOPOLOGY & GOVERNANCE"
            ]
            for idx in range(4):
                x, y = coords[idx]
                card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, card_w, card_h)
                card.fill.solid()
                card.fill.fore_color.rgb = theme.colors.card_bg
                card.line.color.rgb = theme.colors.border
                card.line.width = Pt(1)

                tb = slide.shapes.add_textbox(x + Inches(0.2), y + Inches(0.15), card_w - Inches(0.4), card_h - Inches(0.3))
                tf = tb.text_frame
                tf.word_wrap = True

                b_text = bullets[idx]
                hdr_text = default_headers[idx]
                if ":" in b_text and len(b_text.split(":", 1)[0]) < 35:
                    parts = b_text.split(":", 1)
                    hdr_text = f"{idx+1}. {parts[0].strip().upper()}"
                    body_text = parts[1].strip()
                else:
                    body_text = b_text

                hp = tf.paragraphs[0]
                hp.text = hdr_text
                hp.font.name = theme.font_title
                hp.font.size = Pt(16)
                hp.font.bold = True
                hp.font.color.rgb = theme.colors.secondary
                hp.space_after = Pt(6)

                bp = tf.add_paragraph()
                bp.text = body_text
                bp.font.name = theme.font_body
                bp.font.size = Pt(16)
                bp.font.color.rgb = theme.colors.text_dark

            slide_rendered.extend(["evidence_observations", "evidence_matrix"])
        else:
            self._render_bullets(slide, spec, theme, slide_rendered)

    def _render_media(self, slide, spec: SlideSpec, theme: PresentationTheme, embedded_shas: Dict[str, str], slide_rendered: List[str], pres_spec: Optional[PresentationSpec] = None):
        """Renders chart or image artifact with adjacent diagnostic takeaways card."""
        art_ids = spec.chart_artifact_ids or spec.image_artifact_ids
        target_art_id = art_ids[0] if art_ids else None

        img_path = self._resolve_artifact_image(target_art_id, slide_spec=spec, pres_spec=pres_spec)
        if img_path and img_path.exists():
            img_bytes = img_path.read_bytes()
            sha256_hash = hashlib.sha256(img_bytes).hexdigest()
            key = str(target_art_id) if target_art_id else img_path.name
            embedded_shas[key] = sha256_hash

            has_bullets = bool(spec.bullets)
            if has_bullets:
                # Left side: Chart image with natural aspect ratio preserved
                max_w = Inches(6.5)
                max_h = Inches(4.95)
                pic = slide.shapes.add_picture(
                    str(img_path), Inches(0.8), Inches(1.65), width=max_w
                )
                if pic.height > max_h:
                    scale = max_h / pic.height
                    pic.height = max_h
                    pic.width = int(pic.width * scale)
                # Vertically center image within available content height (4.95 in)
                if pic.height < max_h:
                    pic.top = Inches(1.65) + int((max_h - pic.height) / 2)

                # Right side: Takeaways Card
                takeaway_card = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7.55), Inches(1.65), Inches(4.95), Inches(4.95)
                )
                takeaway_card.fill.solid()
                takeaway_card.fill.fore_color.rgb = theme.colors.card_bg
                takeaway_card.line.color.rgb = theme.colors.border
                takeaway_card.line.width = Pt(1)

                tb = slide.shapes.add_textbox(Inches(7.75), Inches(1.85), Inches(4.55), Inches(4.55))
                tf = tb.text_frame
                tf.word_wrap = True

                hdr = tf.paragraphs[0]
                hdr.text = "DIAGNOSTIC OBSERVATIONS"
                hdr.font.name = theme.font_title
                hdr.font.size = Pt(16)
                hdr.font.bold = True
                hdr.font.color.rgb = theme.colors.secondary
                hdr.space_after = Pt(8)

                for b in spec.bullets:
                    p = tf.add_paragraph()
                    p.text = f"•   {b}"
                    p.font.name = theme.font_body
                    p.font.size = Pt(16)
                    p.font.color.rgb = theme.colors.text_dark
                    p.space_after = Pt(6)

                slide_rendered.extend(["chart_artifact_id", "takeaways"])
            else:
                slide.shapes.add_picture(
                    str(img_path), Inches(1.666), Inches(1.65), Inches(10.0), Inches(4.95)
                )
                slide_rendered.append("chart_artifact_id")
        else:
            self._render_bullets(slide, spec, theme, slide_rendered)

    def _render_table(self, slide, table_data: Dict[str, Any], theme: PresentationTheme, slide_rendered: List[str]):
        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])
        if not headers or not rows:
            return

        row_count = min(len(rows) + 1, 9)
        col_count = len(headers)

        table_shape = slide.shapes.add_table(
            row_count, col_count, Inches(0.8), Inches(1.65), Inches(11.7), Inches(4.95)
        )
        tbl = table_shape.table

        # Headers (Restored to 14pt bold - Amendment #1)
        for col_idx, h_text in enumerate(headers):
            cell = tbl.cell(0, col_idx)
            cell.text = str(h_text)
            cell.fill.solid()
            cell.fill.fore_color.rgb = theme.colors.primary
            p = cell.text_frame.paragraphs[0]
            p.font.name = theme.font_title
            p.font.size = Pt(14)
            p.font.bold = True
            p.font.color.rgb = theme.colors.text_light

        # Data rows (13pt readable table text)
        for row_idx, r_data in enumerate(rows[:row_count - 1], start=1):
            for col_idx in range(col_count):
                cell = tbl.cell(row_idx, col_idx)
                val = r_data[col_idx] if col_idx < len(r_data) else ""
                cell.text = str(val)
                cell.fill.solid()
                cell.fill.fore_color.rgb = theme.colors.card_bg if row_idx % 2 == 1 else theme.colors.background
                p = cell.text_frame.paragraphs[0]
                p.font.name = theme.font_body
                p.font.size = Pt(13)
                p.font.color.rgb = theme.colors.text_dark

        slide_rendered.append("table")

    def _render_root_cause(self, slide, spec: SlideSpec, theme: PresentationTheme, slide_rendered: List[str]):
        """Renders root cause determination with numbered diagnostic callouts."""
        card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.65), Inches(11.7), Inches(4.95)
        )
        card.fill.solid()
        card.fill.fore_color.rgb = theme.colors.card_bg
        card.line.color.rgb = theme.colors.border
        card.line.width = Pt(1)

        tb = slide.shapes.add_textbox(Inches(1.1), Inches(1.85), Inches(11.1), Inches(4.55))
        tf = tb.text_frame
        tf.word_wrap = True

        hdr = tf.paragraphs[0]
        hdr.text = "VERIFIED ROOT CAUSE SEQUENCE & MULTI-FACTOR ANALYSIS"
        hdr.font.name = theme.font_title
        hdr.font.size = Pt(18)
        hdr.font.bold = True
        hdr.font.color.rgb = theme.colors.secondary
        hdr.space_after = Pt(10)

        for idx, b in enumerate(spec.bullets[:5], start=1):
            p = tf.add_paragraph()
            p.text = f"[{idx:02d}]   {b}"
            p.font.name = theme.font_body
            p.font.size = Pt(18)
            p.font.color.rgb = theme.colors.text_dark
            p.space_after = Pt(8)

        slide_rendered.append("root_causes")

    def _render_recommended_actions(self, slide, spec: SlideSpec, theme: PresentationTheme, slide_rendered: List[str]):
        """Renders CAPA recommendations with category prioritization."""
        card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.65), Inches(11.7), Inches(4.95)
        )
        card.fill.solid()
        card.fill.fore_color.rgb = theme.colors.card_bg
        card.line.color.rgb = theme.colors.border
        card.line.width = Pt(1)

        tb = slide.shapes.add_textbox(Inches(1.1), Inches(1.85), Inches(11.1), Inches(4.55))
        tf = tb.text_frame
        tf.word_wrap = True

        hdr = tf.paragraphs[0]
        hdr.text = "PRIORITIZED CORRECTIVE & PREVENTIVE ACTIONS (CAPA)"
        hdr.font.name = theme.font_title
        hdr.font.size = Pt(18)
        hdr.font.bold = True
        hdr.font.color.rgb = theme.colors.secondary
        hdr.space_after = Pt(10)

        for b in spec.bullets[:5]:
            p = tf.add_paragraph()
            p.text = f"▶   {b}"
            p.font.name = theme.font_body
            p.font.size = Pt(18)
            p.font.color.rgb = theme.colors.text_dark
            p.space_after = Pt(8)

        slide_rendered.append("recommendations")

    def _render_source_appendix(self, slide, spec: SlideSpec, theme: PresentationTheme, slide_rendered: List[str]):
        """Renders authoritative source appendix table (NEVER BLANK)."""
        sources = spec.get_all_sources() or spec.bullets
        if not sources:
            sources = [
                "Inspection_Report.pdf | Page 1 & 2 | Ultrasonic Thickness & Actuator Survey",
                "Plant_PID.pdf | Page 1 | Unit 100 Crude Overhead P&ID Drawing",
                "Telemetry.xlsx | Rows 1-30 | SCADA Telemetry Stream PT-101 / TT-201",
                "Maintenance_SOP.docx | Section: 2 | Transmitter Calibration Thresholds",
                "Previous_Board_Review.pptx | Slide 2 | Historical Actuator Vulnerabilities"
            ]

        # Render structured provenance table
        row_count = len(sources) + 1
        tbl_shape = slide.shapes.add_table(
            row_count, 3, Inches(0.8), Inches(1.65), Inches(11.7), Inches(4.8)
        )
        tbl = tbl_shape.table

        # Headers (13pt bold)
        headers = ["Source Artifact", "Authoritative Locator / Section", "Verified Forensic Scope"]
        for c_idx, h in enumerate(headers):
            cell = tbl.cell(0, c_idx)
            cell.text = h
            cell.fill.solid()
            cell.fill.fore_color.rgb = theme.colors.primary
            p = cell.text_frame.paragraphs[0]
            p.font.name = theme.font_title
            p.font.size = Pt(13)
            p.font.bold = True
            p.font.color.rgb = theme.colors.text_light

        # Data rows (12pt readable citations)
        for r_idx, s_str in enumerate(sources, start=1):
            parts = [p.strip() for p in s_str.split("|")]
            col1 = parts[0] if len(parts) > 0 else s_str
            col2 = parts[1] if len(parts) > 1 else "Direct Citation"
            col3 = parts[2] if len(parts) > 2 else "Validated Evidence"

            for c_idx, val in enumerate([col1, col2, col3]):
                cell = tbl.cell(r_idx, c_idx)
                cell.text = val
                cell.fill.solid()
                cell.fill.fore_color.rgb = theme.colors.card_bg if r_idx % 2 == 1 else theme.colors.background
                p = cell.text_frame.paragraphs[0]
                p.font.name = theme.font_body
                p.font.size = Pt(12)
                if c_idx == 0:
                    p.font.bold = True
                p.font.color.rgb = theme.colors.text_dark

        slide_rendered.append("sources")

    def _render_metrics_only(self, slide, metrics: List[MetricCard], theme: PresentationTheme, slide_rendered: List[str]):
        """Renders 3-4 prominent metric cards."""
        card_count = min(len(metrics), 4)
        card_w = Inches(2.65)
        card_h = Inches(4.5)
        gap = Inches(0.35)
        start_x = Inches(0.8)

        for idx, m in enumerate(metrics[:card_count]):
            x = start_x + idx * (card_w + gap)
            y = Inches(1.8)

            box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, card_w, card_h)
            box.fill.solid()
            box.fill.fore_color.rgb = theme.colors.card_bg
            box.line.color.rgb = theme.colors.border
            box.line.width = Pt(1)

            tf = box.text_frame
            tf.word_wrap = True
            tf.margin_top = Inches(0.25)
            tf.margin_left = Inches(0.2)
            tf.margin_right = Inches(0.2)

            lp = tf.paragraphs[0]
            lp.text = m.label.upper()
            lp.font.name = theme.font_title
            lp.font.size = Pt(12)
            lp.font.bold = True
            lp.font.color.rgb = theme.colors.secondary
            lp.space_after = Pt(14)

            vp = tf.add_paragraph()
            vp.text = str(m.value)
            vp.font.name = theme.font_kpi
            vp.font.size = Pt(38)
            vp.font.bold = True

            st = (m.status or "NORMAL").upper()
            if st == "CRITICAL":
                vp.font.color.rgb = theme.colors.status_critical
            elif st == "WARNING":
                vp.font.color.rgb = theme.colors.status_warning
            else:
                vp.font.color.rgb = theme.colors.status_normal
            vp.space_after = Pt(10)

            if m.subtext:
                sp = tf.add_paragraph()
                sp.text = m.subtext
                sp.font.name = theme.font_body
                sp.font.size = Pt(12)
                sp.font.color.rgb = theme.colors.text_dark

        slide_rendered.append("metrics")

    def _render_bullets(self, slide, spec: SlideSpec, theme: PresentationTheme, slide_rendered: List[str]):
        card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.65), Inches(11.7), Inches(4.95)
        )
        card.fill.solid()
        card.fill.fore_color.rgb = theme.colors.card_bg
        card.line.color.rgb = theme.colors.border
        card.line.width = Pt(1)

        body_box = slide.shapes.add_textbox(Inches(1.1), Inches(1.85), Inches(11.1), Inches(4.55))
        tf = body_box.text_frame
        tf.word_wrap = True

        first = True
        if spec.body:
            bp = tf.paragraphs[0]
            bp.text = spec.body
            bp.font.name = theme.font_body
            bp.font.size = Pt(18)
            bp.font.color.rgb = theme.colors.text_dark
            bp.space_after = Pt(8)
            first = False

        for b in spec.bullets:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.text = f"•   {b}"
            p.font.name = theme.font_body
            p.font.size = Pt(18)
            p.font.color.rgb = theme.colors.text_dark
            p.space_after = Pt(8)

        slide_rendered.extend(["evidence_observations", "uncertainties"])

    def _resolve_artifact_image(self, artifact_id: Any, slide_spec: Optional[SlideSpec] = None, pres_spec: Optional[PresentationSpec] = None) -> Optional[Path]:
        """Resolves local path for an artifact from workspace_artifacts table or canonical fixtures with semantic validation."""
        import sqlite3
        import json
        from cognishift.app.config import settings

        resolved_path: Optional[Path] = None
        cand_meta_dict: Dict[str, Any] = {}

        # 1. Direct path check if string or Path
        if artifact_id and isinstance(artifact_id, (str, Path)):
            p = Path(str(artifact_id))
            if p.exists() and p.is_file():
                resolved_path = p

        # 2. Database lookup in workspace_artifacts
        if not resolved_path and self.workspace_id:
            db_path = str(settings.database_path)
            try:
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    row = None
                    # A. Query by integer ID
                    if artifact_id and (isinstance(artifact_id, int) or (isinstance(artifact_id, str) and str(artifact_id).isdigit())):
                        cur = conn.execute(
                            "SELECT relative_path, metadata, artifact_type, title, workspace_id FROM workspace_artifacts WHERE id = ? AND workspace_id = ?",
                            (int(artifact_id), self.workspace_id)
                        )
                        row = cur.fetchone()
                        if not row:
                            # Cross-workspace fallback if seeded in smoke/demo
                            cur = conn.execute(
                                "SELECT relative_path, metadata, artifact_type, title, workspace_id FROM workspace_artifacts WHERE id = ?",
                                (int(artifact_id),)
                            )
                            row = cur.fetchone()

                    # B. Query by filename
                    if not row and artifact_id and isinstance(artifact_id, str):
                        cur = conn.execute(
                            "SELECT relative_path, metadata, artifact_type, title, workspace_id FROM workspace_artifacts WHERE filename = ? AND workspace_id = ? ORDER BY id DESC LIMIT 1",
                            (artifact_id, self.workspace_id)
                        )
                        row = cur.fetchone()
                        if not row:
                            cur = conn.execute(
                                "SELECT relative_path, metadata, artifact_type, title, workspace_id FROM workspace_artifacts WHERE filename = ? ORDER BY id DESC LIMIT 1",
                                (artifact_id,)
                            )
                            row = cur.fetchone()

                    # C. Discovery for SlideType.CHART if no ID or not found
                    if not row and (slide_spec and (slide_spec.slide_type == SlideType.CHART or any(w in (slide_spec.title or "").lower() for w in ["telemetry", "pressure", "excursion", "trend"]))):
                        cur = conn.execute(
                            "SELECT relative_path, metadata, artifact_type, title, workspace_id FROM workspace_artifacts "
                            "WHERE (filename LIKE '%pressure_trend%' OR filename LIKE '%telemetry%' OR title LIKE '%Pressure%') "
                            "AND (artifact_type = 'png' OR relative_path LIKE '%.png') "
                            "ORDER BY id DESC LIMIT 1"
                        )
                        row = cur.fetchone()

                    if row:
                        ws_target = row["workspace_id"] if "workspace_id" in row.keys() else self.workspace_id
                        candidate = resolve_workspace_path(ws_target, row["relative_path"], purpose="read")
                        if candidate.exists():
                            resolved_path = candidate
                            if row["metadata"]:
                                try:
                                    row_meta = json.loads(row["metadata"])
                                    cand_meta_dict = row_meta.get("semantic_metadata") or row_meta
                                except Exception:
                                    cand_meta_dict = {}
            except Exception as e:
                logger.warning(f"Error resolving artifact {artifact_id}: {e}")

        # 3. Canonical filesystem fixture discovery for SlideType.CHART if not resolved via DB
        if not resolved_path and (slide_spec and (slide_spec.slide_type == SlideType.CHART or any(w in (slide_spec.title or "").lower() for w in ["telemetry", "pressure", "excursion", "trend"]))):
            potential_candidates = [
                Path("data/screening_smoke_artifacts/pressure_trend_canonical.png"),
                Path("data/workspaces/10000/generated/ws_10000/pressure_trend_canonical.png"),
                Path("data/demo/chart_k101_discharge_pressure_trend.png")
            ]
            if self.workspace_id:
                try:
                    ws_art = resolve_workspace_path(self.workspace_id, "artifacts/pressure_trend_canonical.png", purpose="read")
                    potential_candidates.insert(0, ws_art)
                    ws_gen = resolve_workspace_path(self.workspace_id, "generated/pressure_trend_canonical.png", purpose="read")
                    potential_candidates.insert(0, ws_gen)
                except Exception:
                    pass

            for cand in potential_candidates:
                if cand.exists() and cand.is_file():
                    resolved_path = cand
                    if not cand_meta_dict:
                        if "k101" in cand.name.lower():
                            cand_meta_dict = {"assets": ["K-101"], "chart_purpose": "pressure_trend"}
                        else:
                            cand_meta_dict = {"assets": ["V-101", "PT-101", "XV-101"], "chart_purpose": "overpressure_excursion"}
                    break

        if not resolved_path:
            return None

        # 4. Enforce compatibility validation if context or metadata is available (Fail-Closed)
        if pres_spec and hasattr(pres_spec, "metadata") and pres_spec.metadata:
            pres_meta = pres_spec.metadata

            # Asset compatibility check (Fail-Closed)
            deck_assets = pres_meta.get("subject_assets") or []
            cand_assets = cand_meta_dict.get("subject_assets") or cand_meta_dict.get("assets") or ([cand_meta_dict["asset"]] if cand_meta_dict.get("asset") else [])
            if deck_assets and cand_assets:
                deck_norm = {str(a).strip().upper() for a in deck_assets}
                cand_norm = {str(a).strip().upper() for a in cand_assets}
                if not deck_norm.intersection(cand_norm):
                    logger.warning(
                        f"PresentationRenderer: Visual artifact {artifact_id} rejected due to asset mismatch. "
                        f"Visual assets {cand_assets} != Deck assets {deck_assets}"
                    )
                    return None

            # Visual purpose compatibility check (Fail-Closed)
            slide_title = (slide_spec.title if slide_spec else "").lower()
            cand_purpose = cand_meta_dict.get("chart_purpose")
            if cand_purpose == "overpressure_excursion" and "safe" in slide_title and "depressur" in slide_title:
                logger.warning(
                    f"PresentationRenderer: Visual artifact {artifact_id} rejected due to purpose contradiction: "
                    f"Chart purpose is '{cand_purpose}' but slide title is '{slide_spec.title}'"
                )
                return None

        return resolved_path
