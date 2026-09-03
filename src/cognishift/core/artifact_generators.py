"""
Sovereign Document Generation, Structural Validation, and Artifact Registration Engine.
Phase 3 Implementation for CogniShift.
Zero-cloud, 100% offline generation using python-docx, openpyxl, and python-pptx.
"""

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
        generator_fn(temp_path)

        val_result = validate_artifact_structure(temp_path, artifact_type)
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
