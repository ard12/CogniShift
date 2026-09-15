"""
Office Document Rendering and Extraction Backend for CogniShift.
Provides local sovereign ingestion for:
- DOCX: Native paragraph, table, and section heading extraction via python-docx.
- XLSX: Structured row chunking via openpyxl + pure-Python visual sheet tile rasterization via matplotlib/PIL.
- Cell-level deterministic numeric verification for spreadsheets.
"""
import io
import gc
import hashlib
import tempfile
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import docx
import pptx
import openpyxl
try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None
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

    # Attempt to extract document title
    doc_title = ""
    try:
        if doc.core_properties and doc.core_properties.title:
            doc_title = doc.core_properties.title.strip()
    except Exception:
        doc_title = ""

    current_section = "General"
    current_section_idx = 1
    current_text_parts: List[str] = []
    chunk_counter = 1
    item_counter = 0

    def _flush_section():
        nonlocal current_text_parts, chunk_counter, current_section_idx
        if current_text_parts:
            full_text = "\n\n".join(current_text_parts).strip()
            if full_text:
                chunks.append({
                    "text": full_text,
                    "section_heading": current_section,
                    "section_index": current_section_idx,
                    "document_title": doc_title,
                    "chunk_index": chunk_counter,
                    "filename": file_path.name,
                    "document_type": "docx",
                    "extraction_method": "DOCUMENT",
                    "page": None  # Native DOCX does not have physical page numbers
                })
                chunk_counter += 1
            current_text_parts = []

    for p in doc.paragraphs:
        txt = p.text.strip()
        if not txt:
            continue
        style_name = p.style.name.lower() if p.style else ""
        if "heading" in style_name or style_name.startswith("title"):
            _flush_section()
            current_section = txt
            current_section_idx += 1
            if not doc_title and style_name.startswith("title"):
                doc_title = txt
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


def render_docx_pages(file_path: Path) -> Tuple[List[Tuple[int, bytes]], Dict[str, Any]]:
    """
    Renders each page of a DOCX document to PNG bytes locally.
    Uses Word COM on Windows to convert to intermediate PDF, then renders pages via PyMuPDF.
    Guarantees strict cleanup of temporary files and zero arbitrary command execution.
    Returns ([(page_number, png_bytes), ...], provenance_dict).
    """
    source_sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()
    t_now = datetime.now(timezone.utc).isoformat()

    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        word = None
        doc = None
        pages_out: List[Tuple[int, bytes]] = []
        intermediate_sha: Optional[str] = None
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_p = Path(tmp_dir)
            pdf_path = tmp_p / "rendered_intermediate.pdf"
            try:
                word = win32com.client.Dispatch("Word.Application")
                word.Visible = False
                doc = word.Documents.Open(str(file_path.resolve()))
                doc.SaveAs(str(pdf_path.resolve()), FileFormat=17)  # 17 = wdFormatPDF
                doc.Close()
                doc = None
            finally:
                if doc:
                    try:
                        doc.Close()
                    except Exception:
                        pass
                    doc = None
                if word:
                    try:
                        word.Quit()
                    except Exception:
                        pass
                    word = None
                gc.collect()
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                pdf_bytes = pdf_path.read_bytes()
                intermediate_sha = hashlib.sha256(pdf_bytes).hexdigest()
                if fitz is not None:
                    pdf_doc = fitz.open(str(pdf_path))
                    for i, page in enumerate(pdf_doc, start=1):
                        pix = page.get_pixmap(dpi=150)
                        pages_out.append((i, pix.tobytes("png")))
                    pdf_doc.close()

            if pages_out:
                prov = {
                    "renderer_type": "WORD_COM",
                    "renderer_version": "16.0",
                    "source_sha256": source_sha256,
                    "rendered_intermediate_sha256": intermediate_sha,
                    "render_timestamp": t_now,
                    "page_count": len(pages_out),
                    "render_status": "SUCCESS"
                }
                return pages_out, prov
    except Exception as com_err:
        logger.warning(f"Local Word COM rendering unavailable for {file_path.name}: {com_err}")

    prov_failed = {
        "renderer_type": None,
        "renderer_version": None,
        "source_sha256": source_sha256,
        "rendered_intermediate_sha256": None,
        "render_timestamp": t_now,
        "page_count": 0,
        "render_status": "RENDERER_UNAVAILABLE",
        "error": "No local Word COM renderer available on host."
    }
    return [], prov_failed


def extract_pptx_structured_content(file_path: Path) -> List[Dict[str, Any]]:
    """
    Extracts text, slide titles, tables, shapes, and speaker notes from a PPTX presentation.
    Preserves 1-indexed slide boundaries.
    Returns a list of structured chunk dicts.
    """
    prs = pptx.Presentation(str(file_path))
    chunks: List[Dict[str, Any]] = []

    for slide_idx, slide in enumerate(prs.slides, start=1):
        # 1. Slide Title
        slide_title = ""
        try:
            if slide.shapes.title and slide.shapes.title.text:
                slide_title = slide.shapes.title.text.strip()
        except Exception:
            slide_title = ""

        if not slide_title and slide.shapes:
            for sh in slide.shapes:
                if sh.has_text_frame and sh.text_frame.text.strip():
                    slide_title = sh.text_frame.text.strip().split("\n")[0]
                    break
        if not slide_title:
            slide_title = f"Slide {slide_idx}"

        # 2. Text shapes and paragraphs
        body_parts: List[str] = []
        table_parts: List[str] = []
        table_count = 0

        for shape in slide.shapes:
            # Avoid repeating slide title verbatim
            if hasattr(slide.shapes, "title") and shape == slide.shapes.title:
                continue

            if shape.has_text_frame:
                txt = shape.text_frame.text.strip()
                if txt and txt != slide_title:
                    body_parts.append(txt)

            elif shape.has_table:
                table_count += 1
                table = shape.table
                t_rows = []
                for row in table.rows:
                    t_rows.append([cell.text.strip() for cell in row.cells])
                if t_rows:
                    hdr = t_rows[0]
                    data = t_rows[1:] if len(t_rows) > 1 else t_rows
                    t_lines = [" | ".join(hdr), " | ".join(["---"] * len(hdr))]
                    for dr in data:
                        t_lines.append(" | ".join(dr))
                    table_parts.append(f"[Table {table_count}]\n" + "\n".join(t_lines))

        # 3. Speaker notes
        notes_text = None
        notes_status = "NOT_PRESENT"
        try:
            if slide.has_notes_slide:
                ntf = slide.notes_slide.notes_text_frame
                if ntf and ntf.text and ntf.text.strip():
                    notes_text = ntf.text.strip()
                    notes_status = "SUPPORTED"
        except Exception as ne:
            logger.warning(f"Error extracting speaker notes for slide {slide_idx}: {ne}")
            notes_status = "DEGRADED"

        # 4. Construct unified slide chunk text
        chunk_lines = [f"### SLIDE {slide_idx}: {slide_title}"]
        if body_parts:
            chunk_lines.append("\n\n".join(body_parts))
        if table_parts:
            chunk_lines.append("\n\n".join(table_parts))
        if notes_text:
            chunk_lines.append(f"[Speaker Notes]: {notes_text}")

        full_text = "\n\n".join(chunk_lines).strip()
        chunks.append({
            "text": full_text,
            "slide_number": slide_idx,
            "slide_title": slide_title,
            "filename": file_path.name,
            "document_type": "pptx",
            "element_type": "slide",
            "chunk_index": slide_idx,
            "extraction_method": "PRESENTATION",
            "notes_status": notes_status,
            "notes": notes_text,
            "has_notes": bool(notes_text and notes_text.strip()),
            "table_count": table_count,
            "has_tables": table_count > 0,
            "shape_count": len(slide.shapes),
            "page": slide_idx  # For general locator fallback, but slide_number is authoritative
        })

    return chunks


def render_pptx_slides(file_path: Path) -> Tuple[List[Tuple[int, bytes]], Dict[str, Any]]:
    """
    Renders each slide of a PPTX file to PNG bytes locally.
    Uses PowerPoint COM on Windows if available.
    Guarantees strict cleanup of temporary files and zero arbitrary command execution.
    Returns ([(slide_number, png_bytes), ...], provenance_dict).
    """
    source_sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()
    t_now = datetime.now(timezone.utc).isoformat()

    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        ppt = None
        presentation = None
        slides_out: List[Tuple[int, bytes]] = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_p = Path(tmp_dir)
            try:
                ppt = win32com.client.Dispatch("PowerPoint.Application")
                presentation = ppt.Presentations.Open(
                    str(file_path.resolve()),
                    ReadOnly=True,
                    Untitled=False,
                    WithWindow=False
                )
                slide_count = presentation.Slides.Count
                for i in range(1, slide_count + 1):
                    out_png = tmp_p / f"slide_{i}.png"
                    presentation.Slides(i).Export(str(out_png), "PNG", 1920, 1080)
                    if out_png.exists() and out_png.stat().st_size > 0:
                        slides_out.append((i, out_png.read_bytes()))

                presentation.Close()
                presentation = None
            finally:
                if presentation:
                    try:
                        presentation.Close()
                    except Exception:
                        pass
                    presentation = None
                if ppt:
                    try:
                        ppt.Quit()
                    except Exception:
                        pass
                    ppt = None
                gc.collect()
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

            if slides_out:
                prov = {
                    "renderer_type": "POWERPOINT_COM",
                    "renderer_version": "16.0",
                    "source_sha256": source_sha256,
                    "rendered_intermediate_sha256": None,
                    "render_timestamp": t_now,
                    "slide_count": len(slides_out),
                    "render_status": "SUCCESS"
                }
                return slides_out, prov
    except Exception as com_err:
        logger.warning(f"Local PowerPoint COM rendering unavailable for {file_path.name}: {com_err}")

    prov_failed = {
        "renderer_type": None,
        "renderer_version": None,
        "source_sha256": source_sha256,
        "rendered_intermediate_sha256": None,
        "render_timestamp": t_now,
        "slide_count": 0,
        "render_status": "RENDERER_UNAVAILABLE",
        "error": "No local PowerPoint COM renderer available on host."
    }
    return [], prov_failed


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

            from openpyxl.utils import get_column_letter
            total_cols = len(headers)
            col_start = get_column_letter(1)
            col_end = get_column_letter(max(1, total_cols))

            text_chunk = "\n".join(md_lines)
            meta = {
                "filename": file_path.name,
                "sheet_name": sheet_name,
                "row_start": row_start,
                "row_end": row_end,
                "col_start": col_start,
                "col_end": col_end,
                "page": tile_page_counter,
                "extraction_method": "SPREADSHEET",
                "processing_version": "v1"
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
