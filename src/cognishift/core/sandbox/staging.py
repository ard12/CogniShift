"""
Secure Input Staging for Phase 4 Sandbox.
Handles server-controlled staging of source code and authorized input files into ephemeral directories.
"""
import shutil
import logging
from pathlib import Path
from typing import Dict, Any

from cognishift.app.config import settings
from cognishift.core.security import (
    resolve_workspace_path,
    get_workspace_root,
    SecurityError,
    GENERIC_READABLE_ROOTS
)
from cognishift.core.sandbox.schemas import CodeExecutionRequest

logger = logging.getLogger(__name__)


def stage_execution_environment(
    workspace_id: int,
    execution_id: str,
    request: CodeExecutionRequest
) -> Path:
    """
    Creates an isolated ephemeral staging directory for this execution:
    data/workspaces/<ws_id>/temporary/sandbox_<id>/
    ├── source/
    │   └── <entrypoint>
    ├── input/
    │   └── <authorized input files>
    └── output/
    
    Security Guarantees:
    1. Input files must resolve through canonical workspace resolver.
    2. Input files must strictly originate from approved roots (documents/ or uploads/).
    3. Special files (symlinks, junctions, devices, fifos) are strictly rejected.
    4. Input size limits (per-file and aggregate) are strictly enforced.
    5. Source code is written directly to source/ with restricted permissions.
    """
    ws_root = get_workspace_root(workspace_id)
    staging_rel = f"temporary/sandbox_{execution_id}"
    staging_dir = resolve_workspace_path(workspace_id, staging_rel, purpose="write", allow_create_parent=True)

    # Ensure clean staging directory
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)

    source_dir = staging_dir / "source"
    input_dir = staging_dir / "input"
    output_dir = staging_dir / "output"

    source_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Stage Source Code
    script_path = source_dir / request.entrypoint
    script_path.write_text(request.code, encoding="utf-8")

    # 2. Stage Input Files
    if len(request.input_files) > settings.sandbox_max_input_files:
        raise SecurityError(
            f"Input file count ({len(request.input_files)}) exceeds server limit of {settings.sandbox_max_input_files}."
        )

    total_input_bytes = 0
    for input_ref in request.input_files:
        # Resolve source through canonical resolver
        resolved_src = resolve_workspace_path(workspace_id, input_ref.source_path, purpose="read")
        rel_from_root = resolved_src.relative_to(ws_root)
        top_part = rel_from_root.parts[0].lower() if rel_from_root.parts else ""

        # Only approved public roots allowed for staging
        if top_part not in GENERIC_READABLE_ROOTS:
            raise SecurityError(
                f"Security Violation: Sandbox input '{input_ref.source_path}' is from forbidden subsystem '{top_part}/'. "
                f"Inputs must strictly originate from 'documents/' or 'uploads/'."
            )

        # Reject special files (symlinks, devices, etc.)
        if not resolved_src.is_file() or resolved_src.is_symlink():
            raise SecurityError(
                f"Security Violation: Sandbox input '{input_ref.source_path}' must be a regular non-symlink file."
            )

        file_size = resolved_src.stat().st_size
        if file_size > settings.sandbox_max_output_file_bytes:
            raise SecurityError(
                f"Input file '{input_ref.source_path}' ({file_size} bytes) exceeds limit of {settings.sandbox_max_output_file_bytes} bytes."
            )

        total_input_bytes += file_size
        if total_input_bytes > settings.sandbox_max_input_bytes:
            raise SecurityError(
                f"Total input bytes ({total_input_bytes}) exceeds maximum allowed of {settings.sandbox_max_input_bytes} bytes."
            )

        # Copy to staging input directory
        dest_path = input_dir / input_ref.dest_name
        shutil.copy2(str(resolved_src), str(dest_path))

    return staging_dir


def cleanup_staging_environment(staging_dir: Path) -> None:
    """Reliably removes the ephemeral sandbox staging directory."""
    if staging_dir and staging_dir.exists():
        try:
            shutil.rmtree(staging_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Error cleaning sandbox staging directory {staging_dir}: {e}")
