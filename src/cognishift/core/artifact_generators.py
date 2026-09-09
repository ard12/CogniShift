"""
Sovereign Document Generation, Structural Validation, and Artifact Registration Engine.
Phase 3 Implementation for CogniShift.
Zero-cloud, 100% offline generation using python-docx, openpyxl, and python-pptx.
"""

import asyncio
import os
import shutil
import hashlib
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel

import docx
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

import pptx

from cognishift.core.security import (
    resolve_workspace_path,
    ensure_workspace_layout,
    get_workspace_root,
    SecurityError
)
from cognishift.app.db.database import get_db

logger = logging.getLogger(__name__)


class ArtifactValidationResult(BaseModel):
    """Structured result of artifact integrity validation."""
    valid: bool
    sha256_hash: str
    file_size: int
    mime_type: str
    error_message: Optional[str] = None


MIME_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "txt": "text/plain",
    "json": "application/json",
    "csv": "text/csv",
}


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 digest of a local file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_artifact_structure(file_path: Path, artifact_type: str) -> ArtifactValidationResult:
    """
    Exhaustively validates that the generated file is non-empty, structurally sound,
    and readable by the corresponding document package library.
    """
    if not file_path.exists():
        return ArtifactValidationResult(
            valid=False, sha256_hash="", file_size=0,
            mime_type=MIME_TYPES.get(artifact_type, "application/octet-stream"),
            error_message="File does not exist on disk."
        )

    file_size = file_path.stat().st_size
    if file_size == 0:
        return ArtifactValidationResult(
            valid=False, sha256_hash="", file_size=0,
            mime_type=MIME_TYPES.get(artifact_type, "application/octet-stream"),
            error_message="File is empty (0 bytes)."
        )

    sha256_hash = compute_sha256(file_path)
    mime_type = MIME_TYPES.get(artifact_type, "application/octet-stream")

    try:
        if artifact_type == "docx":
            doc = docx.Document(str(file_path))
            _ = len(doc.paragraphs)
        elif artifact_type == "xlsx":
            wb = openpyxl.load_workbook(str(file_path), read_only=True)
            sheet_names = wb.sheetnames
            if not sheet_names:
                raise ValueError("XLSX workbook has no sheets.")
            wb.close()
        elif artifact_type == "pptx":
            prs = pptx.Presentation(str(file_path))
            _ = len(prs.slides)
        elif artifact_type == "pdf":
            import fitz
            pdf_doc = fitz.open(str(file_path))
            if len(pdf_doc) == 0:
                raise ValueError("PDF document has 0 pages.")
            pdf_doc.close()
        elif artifact_type in ["png", "jpg", "jpeg"]:
            from PIL import Image
            with Image.open(str(file_path)) as im:
                im.verify()
        elif artifact_type in ["txt", "json", "csv"]:
            with open(file_path, "r", encoding="utf-8") as f:
                _ = f.read(100)
    except Exception as e:
        logger.warning(f"Structural validation error for {file_path}: {e}")
        return ArtifactValidationResult(
            valid=False, sha256_hash=sha256_hash, file_size=file_size,
            mime_type=mime_type, error_message=f"Structural package validation failed: {str(e)}"
        )

    return ArtifactValidationResult(
        valid=True,
        sha256_hash=sha256_hash,
        file_size=file_size,
        mime_type=mime_type
    )


def generate_docx_document(dest_path: Path, title: str, sections: List[Dict[str, Any]]) -> None:
    """Generate professional formatted DOCX engineering report."""
    doc = docx.Document()
    
    title_p = doc.add_heading(title, level=0)
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    note_p = doc.add_paragraph()
    run = note_p.add_run("CogniShift Sovereign Plant Operations Workbench - Deliverable")
    run.font.size = Pt(9)
    run.font.italic = True
    note_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    for sec in sections:
        heading = sec.get("heading", "Section")
        level = sec.get("level", 1)
        doc.add_heading(heading, level=min(level, 3))

        for p_text in sec.get("paragraphs", []):
            doc.add_paragraph(p_text)

        table_data = sec.get("table")
        if table_data and "headers" in table_data and "rows" in table_data:
            headers = table_data["headers"]
            rows = table_data["rows"]
            table = doc.add_table(rows=1 + len(rows), cols=len(headers))
            table.style = 'Table Grid'
            
            for col_idx, h_text in enumerate(headers):
                cell = table.cell(0, col_idx)
                cell.text = str(h_text)
                for paragraph in cell.paragraphs:
                    for r in paragraph.runs:
                        r.font.bold = True
            
            for row_idx, r_data in enumerate(rows):
                for col_idx, val in enumerate(r_data):
                    if col_idx < len(headers):
                        table.cell(row_idx + 1, col_idx).text = str(val)

        doc.add_paragraph()

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(dest_path))


def sanitize_xlsx_value(val: Any) -> Any:
    """Prevents spreadsheet formula injection by escaping formula starters."""
    if isinstance(val, str):
        if val.startswith(("=", "+", "-", "@")):
            return f"'{val}"
    return val


def generate_xlsx_workbook(dest_path: Path, title: str, sheets: List[Dict[str, Any]]) -> None:
    """Generate structured XLSX workbook with telemetry/tabular data."""
    wb = openpyxl.Workbook()
    default_sheet = wb.active

    for idx, sheet_data in enumerate(sheets):
        name = sheet_data.get("name", f"Sheet{idx+1}")[:31]
        ws = wb.create_sheet(title=name)
        
        ws.cell(row=1, column=1, value=title).font = Font(size=14, bold=True)
        ws.cell(row=2, column=1, value=f"Dataset: {name}").font = Font(size=10, italic=True)

        headers = sheet_data.get("headers", [])
        for c_idx, h_name in enumerate(headers, start=1):
            cell = ws.cell(row=4, column=c_idx, value=str(h_name))
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")

        rows = sheet_data.get("rows", [])
        for r_idx, row_obj in enumerate(rows, start=5):
            cells = row_obj.get("cells", []) if isinstance(row_obj, dict) else row_obj
            for c_idx, cell_val in enumerate(cells, start=1):
                clean_val = sanitize_xlsx_value(cell_val)
                ws.cell(row=r_idx, column=c_idx, value=clean_val)

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    if default_sheet in wb.worksheets:
        wb.remove(default_sheet)

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(dest_path))


def generate_pptx_presentation(dest_path: Path, title: str, subtitle: Optional[str], slides: List[Dict[str, Any]]) -> None:
    """Generate formatted PowerPoint slide presentation."""
    prs = pptx.Presentation()
    
    title_slide_layout = prs.slide_layouts[0]
    title_slide = prs.slides.add_slide(title_slide_layout)
    title_slide.shapes.title.text = title
    if subtitle and title_slide.placeholders and len(title_slide.placeholders) > 1:
        title_slide.placeholders[1].text = subtitle

    bullet_slide_layout = prs.slide_layouts[1]
    for slide_data in slides:
        s_title = slide_data.get("title", "Slide")
        bullet_points = slide_data.get("bullet_points", [])

        slide = prs.slides.add_slide(bullet_slide_layout)
        slide.shapes.title.text = s_title
        tf = slide.shapes.placeholders[1].text_frame
        tf.word_wrap = True

        for b_idx, pt_text in enumerate(bullet_points):
            if b_idx == 0:
                tf.text = pt_text
            else:
                p = tf.add_paragraph()
                p.text = pt_text
                p.level = 0

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(dest_path))


def generate_pdf_document(dest_path: Path, title: str, sections: List[Dict[str, Any]]) -> None:
    """Generate professional formatted PDF engineering report using reportlab."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(dest_path),
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        alignment=1,
        textColor=colors.HexColor('#1F4E79'),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Italic'],
        fontSize=9,
        leading=12,
        alignment=1,
        textColor=colors.HexColor('#555555'),
        spaceAfter=15
    )
    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1F4E79'),
        spaceBefore=10,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['BodyText'],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#222222'),
        spaceAfter=4
    )
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#222222')
    )
    header_cell_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontSize=8,
        leading=11,
        fontName='Helvetica-Bold',
        textColor=colors.white
    )

    story = [
        Paragraph(title, title_style),
        Paragraph("CogniShift Sovereign Plant Operations Workbench - Official Deliverable", subtitle_style),
        Spacer(1, 10)
    ]

    def _clean_pdf_text(text: Any) -> str:
        return str(text).replace("₹", "INR ").replace("€", "EUR ").replace("£", "GBP ")

    for sec in sections:
        heading = _clean_pdf_text(sec.get("heading", "Section"))
        story.append(Paragraph(heading, h1_style))

        for p_text in sec.get("paragraphs", []):
            story.append(Paragraph(_clean_pdf_text(p_text), body_style))

        table_data = sec.get("table")
        if table_data and "headers" in table_data and "rows" in table_data:
            headers = [Paragraph(_clean_pdf_text(h), header_cell_style) for h in table_data["headers"]]
            t_rows = [headers]
            for row in table_data["rows"]:
                t_rows.append([Paragraph(_clean_pdf_text(cell), cell_style) for cell in row])

            col_count = len(table_data["headers"])
            col_width = (letter[0] - 80) / max(col_count, 1)
            t = Table(t_rows, colWidths=[col_width] * col_count)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E79')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D0D0D0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
            ]))
            story.append(Spacer(1, 4))
            story.append(t)
            story.append(Spacer(1, 6))

        story.append(Spacer(1, 6))

    doc.build(story)


def render_document_page_to_image(
    doc_path: Path,
    dest_image_path: Path,
    page_number: int = 1,
    image_format: str = "png",
    dpi: int = 150
) -> Path:
    """Renders a single page of a PDF or spreadsheet document to a PNG or JPEG image file."""
    if not doc_path.exists():
        raise FileNotFoundError(f"Source document '{doc_path}' does not exist.")

    dest_image_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = doc_path.suffix.lower()

    if suffix in [".xlsx", ".xls"]:
        import openpyxl
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        wb = openpyxl.load_workbook(str(doc_path), data_only=True)
        try:
            sheet_names = wb.sheetnames
            if not sheet_names:
                raise ValueError(f"Workbook '{doc_path.name}' contains no sheets.")
            sheet_idx = max(0, min(page_number - 1, len(sheet_names) - 1))
            sheet = wb[sheet_names[sheet_idx]]

            raw_rows = list(sheet.iter_rows(values_only=True))
            if not raw_rows:
                raw_rows = [["(Empty Sheet)"]]

            table_data = []
            for r in raw_rows[:25]:
                row_cells = [str(c) if c is not None else "" for c in r[:10]]
                table_data.append(row_cells)

            fig, ax = plt.subplots(figsize=(12, 7), dpi=dpi)
            ax.axis("off")
            ax.axis("tight")

            headers = [str(h) for h in table_data[0]]
            data_rows = table_data[1:] if len(table_data) > 1 else [[""] * len(headers)]

            table = ax.table(cellText=data_rows, colLabels=headers, loc="center", cellLoc="center")
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1.2, 1.2)
            ax.set_title(f"{doc_path.name} — Sheet: {sheet_names[sheet_idx]}", fontsize=12, pad=12, weight="bold")

            plt.tight_layout()
            save_fmt = "jpeg" if image_format.lower() in ["jpg", "jpeg"] else "png"
            fig.savefig(str(dest_image_path), format=save_fmt, bbox_inches="tight")
            plt.close(fig)
            return dest_image_path
        finally:
            wb.close()

    elif suffix == ".csv":
        import pandas as pd
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        df = pd.read_csv(doc_path)
        fig, ax = plt.subplots(figsize=(12, 7), dpi=dpi)
        ax.axis("off")
        ax.axis("tight")

        headers = list(df.columns)[:10]
        data_rows = [[str(c) if pd.notna(c) else "" for c in r] for r in df.head(25).values[:, :10]]

        table = ax.table(cellText=data_rows, colLabels=headers, loc="center", cellLoc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.2, 1.2)
        ax.set_title(f"{doc_path.name} — Top 25 Rows", fontsize=12, pad=12, weight="bold")

        plt.tight_layout()
        save_fmt = "jpeg" if image_format.lower() in ["jpg", "jpeg"] else "png"
        fig.savefig(str(dest_image_path), format=save_fmt, bbox_inches="tight")
        plt.close(fig)
        return dest_image_path

    else:
        import fitz
        doc = fitz.open(str(doc_path))
        try:
            total_pages = len(doc)
            if total_pages == 0:
                raise ValueError(f"Document '{doc_path.name}' contains zero pages.")
            target_idx = max(0, min(page_number - 1, total_pages - 1))
            page = doc.load_page(target_idx)
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            if image_format.lower() in ["jpg", "jpeg"]:
                pix.save(str(dest_image_path), output="jpeg")
            else:
                pix.save(str(dest_image_path), output="png")
            return dest_image_path
        finally:
            doc.close()


async def create_and_register_artifact(
    workspace_id: int,
    filename: str,
    artifact_type: str,
    generator_fn: Callable[[Path], None],
    title: str,
    description: str = "",
    run_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Atomic artifact creation, structural validation, and SQLite registration lifecycle."""
    ensure_workspace_layout(workspace_id)
    ws_root = get_workspace_root(workspace_id)
    temp_dir = ws_root / "temporary"
    temp_dir.mkdir(parents=True, exist_ok=True)

    if run_id is not None:
        async with get_db() as db:
            c = await db.execute("SELECT workspace_id FROM agent_runs WHERE id = ?", (run_id,))
            run_row = await c.fetchone()
            if not run_row:
                raise SecurityError(f"Run ID {run_id} not found in database.")
            if run_row["workspace_id"] != workspace_id:
                raise SecurityError(f"Cross-workspace run ownership violation: Run {run_id} belongs to workspace {run_row['workspace_id']}, not {workspace_id}.")

    temp_filename = f"temp_{uuid.uuid4().hex}_{filename}"
    temp_path = temp_dir / temp_filename

    try:
        await asyncio.to_thread(generator_fn, temp_path)

        val_result = await asyncio.to_thread(validate_artifact_structure, temp_path, artifact_type)
        if not val_result.valid:
            raise RuntimeError(f"Structural artifact validation failed: {val_result.error_message}")

        if run_id is not None:
            rel_dir = f"generated/run_{run_id}"
        else:
            rel_dir = f"generated/ws_{workspace_id}"

        target_rel_path = f"{rel_dir}/{filename}"
        final_path = resolve_workspace_path(workspace_id, target_rel_path, purpose="write", allow_create_parent=True)

        if final_path.exists():
            dedup_name = f"{Path(filename).stem}_{uuid.uuid4().hex[:6]}{Path(filename).suffix}"
            target_rel_path = f"{rel_dir}/{dedup_name}"
            final_path = resolve_workspace_path(workspace_id, target_rel_path, purpose="write", allow_create_parent=True)

        shutil.move(str(temp_path), str(final_path))

        import json
        meta_json = json.dumps(metadata or {})

        try:
            async with get_db() as db:
                cursor = await db.execute(
                    """INSERT INTO workspace_artifacts
                       (workspace_id, run_id, filename, relative_path, artifact_type, title, description, file_size, sha256_hash, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING *""",
                    (workspace_id, run_id, filename, target_rel_path, artifact_type, title, description, val_result.file_size, val_result.sha256_hash, meta_json)
                )
                row = await cursor.fetchone()
                await db.commit()

                if row and run_id:
                    try:
                        from cognishift.core.notifications import (
                            collect_artifact_evidence,
                            fire_and_forget_notification,
                        )
                        run_info = await (await db.execute("SELECT user_id FROM agent_runs WHERE id = ?", (run_id,))).fetchone()
                        run_user = run_info["user_id"] if run_info else "operator"
                        art_ev = collect_artifact_evidence(
                            run_id=run_id,
                            workspace_id=workspace_id,
                            user_id=run_user,
                            artifact_id=row["id"],
                            artifact_name=filename,
                            artifact_path=target_rel_path,
                        )
                        fire_and_forget_notification(art_ev)
                    except Exception:
                        pass

                return dict(row)
        except Exception as db_err:
            if final_path.exists():
                try:
                    final_path.unlink()
                except Exception:
                    pass
            raise RuntimeError(f"Database artifact registration failed: {str(db_err)}")

    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass


def generate_work_permit_docx(dest_path: Path, permit_data: Dict[str, Any]) -> None:
    """Generate official DOCX temporary operational work permit."""
    doc = docx.Document()
    
    title_p = doc.add_heading("COGNISHIFT SOVEREIGN INDUSTRIAL WORKBENCH", level=0)
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub_p = doc.add_paragraph()
    run = sub_p.add_run("OFFICIAL TEMPORARY OPERATIONAL WORK PERMIT")
    run.font.size = Pt(13)
    run.font.bold = True
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    disclaimer_p = doc.add_paragraph()
    drun = disclaimer_p.add_run("[SIMULATED INDUSTRIAL ACTION - SIH FINALS PROTOTYPE]")
    drun.font.size = Pt(10)
    drun.font.bold = True
    drun.font.italic = True
    disclaimer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()

    # Section 1: Permit Details Table
    doc.add_heading("1. Authorization Parameters & Operational Scope", level=1)
    
    table_data = [
        ["Permit Document Code", permit_data.get("permit_code", "N/A")],
        ["Authorized User (Operator)", permit_data.get("user_id", "N/A")],
        ["Target Asset / Equipment", permit_data.get("resource", "N/A")],
        ["Permitted Operational Action", permit_data.get("action", "N/A")],
        ["Maximum Permitted Uses", str(permit_data.get("max_uses", 1))],
        ["Current Permit Status", permit_data.get("status", "ACTIVE")],
        ["Valid Window (Start UTC)", permit_data.get("valid_from", "N/A")],
        ["Valid Window (Expiry UTC)", permit_data.get("expires_at", "N/A")],
        ["Device Identity Binding", permit_data.get("trusted_device_id") or "Enclave Default (Unbound)"],
    ]

    t1 = doc.add_table(rows=len(table_data), cols=2)
    t1.style = "Table Grid"
    for r_idx, (col1, col2) in enumerate(table_data):
        c1 = t1.cell(r_idx, 0)
        c2 = t1.cell(r_idx, 1)
        c1.text = col1
        c2.text = col2
        for p in c1.paragraphs:
            for r in p.runs:
                r.font.bold = True

    doc.add_paragraph()

    # Section 2: Dual Supervisor Governance
    doc.add_heading("2. Four-Eyes Governance Sign-offs", level=1)
    doc.add_paragraph(
        "In accordance with OISD-STD-240 and CogniShift sovereign governance, this permit requires two independent "
        "authenticated supervisor approvals prior to operational execution:"
    )

    sup1 = permit_data.get("first_approver", "N/A")
    sup1_at = permit_data.get("first_approved_at", "N/A")
    sup2 = permit_data.get("second_approver", "N/A")
    sup2_at = permit_data.get("second_approved_at", "N/A")

    t2 = doc.add_table(rows=3, cols=3)
    t2.style = "Table Grid"
    headers = ["Approval Stage", "Authenticated Supervisor", "Verification Timestamp"]
    for c_idx, h in enumerate(headers):
        cell = t2.cell(0, c_idx)
        cell.text = h
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.bold = True
    
    t2.cell(1, 0).text = "Supervisor Approval 1"
    t2.cell(1, 1).text = f"{sup1} (Authenticated)"
    t2.cell(1, 2).text = str(sup1_at)

    t2.cell(2, 0).text = "Supervisor Approval 2"
    t2.cell(2, 1).text = f"{sup2} (Authenticated)"
    t2.cell(2, 2).text = str(sup2_at)

    doc.add_paragraph()

    # Section 3: Mandatory Safety Interlocks
    doc.add_heading("3. Mandatory Safety Interlocks & Audit Requirements", level=1)
    doc.add_paragraph(
        "• Suction and discharge isolation valves must be in verified positions prior to energization.\n"
        "• High pressure trip threshold: 450.0 PSI (MAWP 500.0 PSI). Temperature trip: 95.0 C.\n"
        "• Single-use permit: this authorization is atomically consumed upon first execution.\n"
        "• Subsequent execution attempts with this permit code will be intercepted and rejected with 403 AUTHORIZATION_CONSUMED."
    )

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(dest_path))


async def generate_and_register_permit_artifact(
    workspace_id: int,
    permit_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate and register the official work permit DOCX artifact."""
    permit_code = permit_data.get("permit_code", "PERMIT")
    filename = f"Work_Permit_{permit_code}.docx"
    title = f"Operational Work Permit: {permit_code}"
    description = (
        f"Official temporary work permit authorizing {permit_data.get('user_id')} "
        f"for action '{permit_data.get('action')}' on asset '{permit_data.get('resource')}'. "
        f"Verified by two independent authenticated supervisor approvals."
    )

    def _gen(dest_path: Path):
        generate_work_permit_docx(dest_path, permit_data)

    artifact_record = await create_and_register_artifact(
        workspace_id=workspace_id,
        filename=filename,
        artifact_type="docx",
        title=title,
        description=description,
        generator_fn=_gen,
        metadata={
            "permit_code": permit_code,
            "user_id": permit_data.get("user_id"),
            "resource": permit_data.get("resource"),
            "action": permit_data.get("action"),
            "status": permit_data.get("status"),
            "simulation": True,
        },
    )
    return artifact_record

