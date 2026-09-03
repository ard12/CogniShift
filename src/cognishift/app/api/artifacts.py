"""
Workspace Artifact REST APIs for CogniShift.
Phase 3 Implementation.
Provides authenticated, IDOR-protected, and tamper-verified artifact listing and downloads.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from typing import List, Optional

from cognishift.app.db.database import get_db
from cognishift.app.db.models import ArtifactResponse, ArtifactListResponse
from cognishift.app.core.auth import get_current_user, verify_workspace_access, User
from cognishift.core.security import resolve_workspace_path, SecurityError
from cognishift.core.artifact_generators import compute_sha256, MIME_TYPES

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/artifacts", tags=["Artifacts"])


@router.get("", response_model=ArtifactListResponse)
async def list_workspace_artifacts(
    workspace_id: int,
    user: User = Depends(get_current_user)
):
    """List all registered artifacts for the specified workspace."""
    verify_workspace_access(workspace_id, user)
    
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM workspace_artifacts
               WHERE workspace_id = ?
               ORDER BY created_at DESC""",
            (workspace_id,)
        )
        rows = await cursor.fetchall()
        artifacts = [ArtifactResponse.model_validate(dict(r)) for r in rows]
        return ArtifactListResponse(total=len(artifacts), artifacts=artifacts)


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact_details(
    workspace_id: int,
    artifact_id: int,
    user: User = Depends(get_current_user)
):
    """Retrieve metadata and SHA-256 checksum for a specific artifact."""
    verify_workspace_access(workspace_id, user)

    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM workspace_artifacts
               WHERE id = ? AND workspace_id = ?""",
            (artifact_id, workspace_id)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact #{artifact_id} not found in workspace {workspace_id}."
            )
        return ArtifactResponse.model_validate(dict(row))


@router.get("/{artifact_id}/download")
async def download_artifact(
    workspace_id: int,
    artifact_id: int,
    user: User = Depends(get_current_user)
):
    """
    Secure file streaming download with SHA-256 tamper verification.
    Refuses download if disk contents do not match registered cryptographic checksum.
    """
    verify_workspace_access(workspace_id, user)

    async with get_db() as db:
        cursor = await db.execute(
            """SELECT * FROM workspace_artifacts
               WHERE id = ? AND workspace_id = ?""",
            (artifact_id, workspace_id)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact #{artifact_id} not found in workspace {workspace_id}."
            )

    # Resolve stored path through canonical security boundary
    try:
        file_path = resolve_workspace_path(workspace_id, row["relative_path"], purpose="read")
    except SecurityError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Path resolution error: {str(e)}")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact payload missing from physical workspace storage."
        )

    # TAMPER DETECTION: Verify file bytes match registered SHA-256 hash
    actual_hash = compute_sha256(file_path)
    registered_hash = row["sha256_hash"]
    if actual_hash != registered_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Tamper detection alert: Artifact #{artifact_id} checksum mismatch! "
                f"Expected registered hash {registered_hash[:16]}..., but computed {actual_hash[:16]}... on disk. "
                f"File delivery refused for security integrity."
            )
        )

    mime_type = MIME_TYPES.get(row["artifact_type"], "application/octet-stream")
    return FileResponse(
        path=str(file_path),
        media_type=mime_type,
        filename=row["filename"],
        headers={
            "X-Checksum-SHA256": registered_hash,
            "Content-Disposition": f'attachment; filename="{row["filename"]}"'
        }
    )
