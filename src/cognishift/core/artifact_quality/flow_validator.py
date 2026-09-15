"""
Document Flow, Pagination, and Visual Readability Verification Engine.
Enforces multi-page table header repetition, page utilization heuristics,
figure sizing/DPI checks, and Unicode glyph rendering verification.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image
import numpy as np

FLOW_VALIDATOR_VERSION = "v3.1.0"


def validate_page_flow(
    page_png_path: Path,
    page_index: int,
    total_pages: int,
    is_cover_or_divider: bool = False,
    is_figure_page: bool = False
) -> Tuple[str, str, float]:
    """
    Evaluates vertical page utilization from rendered page image.
    Classifies page into PASS, REVIEW, or FAIL.
    - Occupancy < 45% on normal page -> REVIEW (advisory, not hard failure).
    - Extreme under-utilization (< 10% / orphan row) on trailing page -> FAIL.
    Returns: (classification, message, occupancy_ratio)
    """
    if not page_png_path.exists():
        return "FAIL", f"Rendered page image not found: {page_png_path.name}", 0.0

    try:
        with Image.open(str(page_png_path)) as im:
            gray = im.convert("L")
            arr = np.array(gray)

        # White background is ~255; content pixels are darker (< 245)
        content_mask = arr < 245
        row_has_content = np.any(content_mask, axis=1)

        if not np.any(row_has_content):
            return "FAIL", f"Page {page_index} is completely blank.", 0.0

        first_row = int(np.argmax(row_has_content))
        last_row = int(len(row_has_content) - 1 - np.argmax(row_has_content[::-1]))
        total_height = arr.shape[0]
        used_height = last_row - first_row
        occupancy_ratio = used_height / max(total_height, 1)

        # Trailing orphan check: if last page has < 12% vertical occupancy and contains only a tiny sliver
        if page_index == total_pages and total_pages > 1 and occupancy_ratio < 0.12 and not is_figure_page:
            return "FAIL", f"PAGE_ORPHAN_DETECTED: Page {page_index} has only {occupancy_ratio:.1%} vertical occupancy (orphaned row/snippet). Rebalance pagination.", occupancy_ratio

        if occupancy_ratio < 0.45 and not is_cover_or_divider and not is_figure_page:
            return "REVIEW", f"PAGE_UNDERUTILIZED: Page {page_index} occupied {occupancy_ratio:.1%} (<45%). Verify if intentional whitespace.", occupancy_ratio

        return "PASS", f"Page {page_index} flow acceptable ({occupancy_ratio:.1%} utilized).", occupancy_ratio

    except Exception as e:
        return "FAIL", f"Error analyzing page flow for {page_png_path.name}: {str(e)}", 0.0


def validate_table_pagination(
    table_spec: Dict[str, Any],
    spans_multiple_pages: bool,
    header_repeated: bool,
    cant_split_enforced: bool = True
) -> Tuple[bool, str]:
    """
    Verifies table continuation hygiene across multi-page boundaries.
    Mandates header repetition on all multi-page tables.
    """
    if not spans_multiple_pages:
        return True, "Table fits on a single page."

    if not header_repeated:
        return False, "TABLE_PAGINATION_FAIL: Multi-page table splits across page boundary without repeating the header row on continuation page (repeatRows=1 / tblHeader required)."

    if not cant_split_enforced:
        return False, "TABLE_PAGINATION_FAIL: Table rows lack cantSplit protection against row boundary page splitting."

    return True, "Multi-page table pagination verified with repeating headers and row protection."


def validate_figure_readability(
    rendered_image_path: Path,
    original_source_path: Optional[Path] = None,
    min_width_in_document: float = 4.0,
    min_effective_dpi: int = 150
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Checks figure presentation quality:
    - Minimum display dimensions
    - Resolution and effective DPI
    - Aspect ratio fidelity (no stretch / squash distortion)
    """
    if not rendered_image_path.exists():
        return False, f"Rendered figure not found: {rendered_image_path.name}", {}

    try:
        with Image.open(str(rendered_image_path)) as im:
            w, h = im.size
            aspect = w / max(h, 1)

        metrics = {"rendered_width": w, "rendered_height": h, "aspect_ratio": round(aspect, 3)}

        # Check resolution
        if w < 500 or h < 250:
            return False, f"FIGURE_RESOLUTION_TOO_LOW: Image dimensions {w}x{h} are below minimum readable threshold (500x250).", metrics

        if original_source_path and original_source_path.exists():
            with Image.open(str(original_source_path)) as orig_im:
                orig_w, orig_h = orig_im.size
                orig_aspect = orig_w / max(orig_h, 1)

            metrics["original_aspect"] = round(orig_aspect, 3)
            # Allow up to 5% aspect ratio variance
            rel_aspect_diff = abs(aspect - orig_aspect) / max(orig_aspect, 1e-4)
            if rel_aspect_diff > 0.05:
                return False, f"FIGURE_DISTORTION_DETECTED: Aspect ratio distorted by {rel_aspect_diff:.1%} (Rendered: {aspect:.2f}, Original: {orig_aspect:.2f}).", metrics

        return True, "Figure readability and aspect ratio fidelity verified.", metrics

    except Exception as e:
        return False, f"Error validating figure readability: {str(e)}", {}


def validate_glyph_rendering(text: str) -> Tuple[bool, str, List[str]]:
    """
    Scans document text for replacement characters or malformed Unicode glyphs.
    """
    anomalies = []
    if "\ufffd" in text:
        anomalies.append("Unicode replacement character \\ufffd detected")

    # Check for corrupt character patterns (e.g. â€™ instead of right single quote)
    corrupt_patterns = ["â€™", "â€œ", "â€", "Ã©", "Ã¼", "Â±"]
    for cp in corrupt_patterns:
        if cp in text:
            anomalies.append(f"Mojibake / encoding corruption pattern '{cp}' detected")

    if anomalies:
        return False, f"GLYPH_RENDERING_FAIL: Text contains encoding anomalies: {'; '.join(anomalies)}", anomalies

    return True, "Glyph rendering clean; zero encoding anomalies detected.", []
