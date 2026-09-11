"""
Office Document Rendering and Extraction Backend for CogniShift.
Provides local sovereign ingestion for:
- DOCX: Native paragraph, table, and section heading extraction via python-docx.
- XLSX: Structured row chunking via openpyxl + pure-Python visual sheet tile rasterization via matplotlib/PIL.
- Cell-level deterministic numeric verification for spreadsheets.
"""
import io
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import docx
import openpyxl
import matplotlib
matplotlib.use("Agg")  # Headless backend
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def render_table_to_png_bytes(
    headers: List[str],
    rows: List[List[Any]],
    title: str = "",
    figsize: Tuple[float, float] = (11.0, 7.5),
    dpi: int = 150
) -> bytes:
    """
    Renders tabular data as a clean, high-contrast engineering sheet tile image.
    Preserves column headers, row lines, and cell readability for visual inspection.
    """
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.axis("tight")
    ax.axis("off")

    if title:
        ax.set_title(title, fontsize=12, fontweight="bold", pad=12, color="#1e293b")

    # Format cell values safely
    str_rows = []
    for r in rows:
        str_rows.append([str(c) if c is not None else "" for c in r])

    if not str_rows:
        str_rows = [["(No Data)"] * max(len(headers), 1)]

    table = ax.table(
        cellText=str_rows,
        colLabels=headers if headers else None,
        loc="center",
        cellLoc="left"
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.3)

    # Style header and rows
    for (row_idx, col_idx), cell in table.get_celld().items():
        if row_idx == 0 and headers:
            cell.set_facecolor("#334155")
            cell.get_text().set_color("#ffffff")
            cell.get_text().set_weight("bold")
        elif row_idx % 2 == 0:
            cell.set_facecolor("#f8fafc")
        else:
            cell.set_facecolor("#ffffff")
        cell.set_edgecolor("#cbd5e1")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=dpi)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def extract_docx_structured_content(file_path: Path) -> List[Dict[str, Any]]:
    """
    Extracts text, headings, and tables from a DOCX document, preserving section hierarchy.
    Returns a list of structured chunk dicts.
    """
    doc = docx.Document(str(file_path))
    chunks: List[Dict[str, Any]] = []

    current_section = "General"
    current_text_parts: List[str] = []
    approx_page = 1
    item_counter = 0

    def _flush_section():
        nonlocal current_text_parts, approx_page
        if current_text_parts:
            full_text = "\n\n".join(current_text_parts).strip()
            if full_text:
                chunks.append({
                    "text": full_text,
                    "section_heading": current_section,
                    "page": approx_page,
                    "filename": file_path.name,
                    "extraction_method": "DOCUMENT"
                })
            current_text_parts = []
            approx_page += 1

    for p in doc.paragraphs:
        txt = p.text.strip()
        if not txt:
            continue
        style_name = p.style.name.lower() if p.style else ""
        if "heading" in style_name or style_name.startswith("title"):
            _flush_section()
            current_section = txt
        else:
            current_text_parts.append(txt)
            item_counter += 1
            if item_counter >= 8:
                _flush_section()
                item_counter = 0

    # Extract tables
    for t_idx, table in enumerate(doc.tables, 1):
        t_rows = []
        for row in table.rows:
            t_rows.append([cell.text.strip() for cell in row.cells])
        if t_rows:
            header_row = t_rows[0]
            data_rows = t_rows[1:] if len(t_rows) > 1 else t_rows
            t_lines = [" | ".join(header_row), " | ".join(["---"] * len(header_row))]
            for dr in data_rows:
                t_lines.append(" | ".join(dr))
            table_md = "\n".join(t_lines)
            current_text_parts.append(f"[Table {t_idx}]\n{table_md}")
            _flush_section()

    _flush_section()
    return chunks


def extract_xlsx_structured_content(
    file_path: Path,
    chunk_row_size: int = 30
) -> Tuple[List[Dict[str, Any]], List[Tuple[bytes, Dict[str, Any]]]]:
    """
    Extracts structured text chunks and visual sheet tile images from an XLSX workbook.
    Returns (text_chunks, visual_tiles).
    """
    wb = openpyxl.load_workbook(str(file_path), data_only=True)
    text_chunks: List[Dict[str, Any]] = []
    visual_tiles: List[Tuple[bytes, Dict[str, Any]]] = []

    tile_page_counter = 1

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        all_rows = list(ws.iter_rows(values_only=True))
        if not all_rows:
            continue

        # Find header row
        header_row_idx = 0
        while header_row_idx < len(all_rows) and not any(all_rows[header_row_idx]):
            header_row_idx += 1

        if header_row_idx >= len(all_rows):
            continue

        headers = [str(c).strip() if c is not None else f"Col_{i+1}" for i, c in enumerate(all_rows[header_row_idx])]
        data_rows = all_rows[header_row_idx + 1:]
        if not data_rows:
            continue

        # Chunk into slices of chunk_row_size
        for chunk_idx in range(0, len(data_rows), chunk_row_size):
            slice_rows = data_rows[chunk_idx:chunk_idx + chunk_row_size]
            row_start = header_row_idx + 2 + chunk_idx
            row_end = row_start + len(slice_rows) - 1

            # Build markdown text chunk
            md_lines = [
                f"### SPREADSHEET: {file_path.name} | Sheet: {sheet_name} | Rows {row_start}-{row_end}",
                " | ".join(headers),
                " | ".join(["---"] * len(headers))
            ]
            for r in slice_rows:
                row_str = [str(c) if c is not None else "" for c in r]
                md_lines.append(" | ".join(row_str))

            text_chunk = "\n".join(md_lines)
            meta = {
                "filename": file_path.name,
                "sheet_name": sheet_name,
                "row_start": row_start,
                "row_end": row_end,
                "page": tile_page_counter,
                "extraction_method": "SPREADSHEET"
            }
            text_chunks.append({
                "text": text_chunk,
                **meta
            })

            # Render visual sheet tile
            try:
                # Limit columns to top 10 for clean visual rendering
                render_headers = headers[:10]
                render_rows = [r[:10] for r in slice_rows[:25]]
                tile_title = f"{file_path.name} — {sheet_name} (Rows {row_start}-{row_end})"
                png_bytes = render_table_to_png_bytes(render_headers, render_rows, title=tile_title)
                visual_tiles.append((png_bytes, meta))
            except Exception as e:
                logger.warning(f"Failed rasterizing sheet tile for {sheet_name} rows {row_start}-{row_end}: {e}")

            tile_page_counter += 1

    wb.close()
    return text_chunks, visual_tiles


async def render_xlsx_tile_bytes(file_path: Path, tile_index: int = 0) -> Optional[bytes]:
    """Helper to render a specific XLSX sheet tile on demand."""
    import asyncio
    def _render():
        _, tiles = extract_xlsx_structured_content(file_path)
        if 0 <= tile_index < len(tiles):
            return tiles[tile_index][0]
        elif tiles:
            return tiles[0][0]
        return None
    return await asyncio.to_thread(_render)


def verify_xlsx_cell(file_path: Path, sheet_name: str, cell_coord: str) -> Dict[str, Any]:
    """
    Direct, deterministic numeric cell-level verification.
    Opens workbook with data_only=True and returns the cell's evaluated value.
    """
    wb = openpyxl.load_workbook(str(file_path), data_only=True)
    try:
        if sheet_name not in wb.sheetnames:
            return {"error": f"Sheet '{sheet_name}' not found", "found": False}
        ws = wb[sheet_name]
        val = ws[cell_coord].value
        return {
            "found": True,
            "filename": file_path.name,
            "sheet": sheet_name,
            "cell": cell_coord,
            "value": val
        }
    finally:
        wb.close()
