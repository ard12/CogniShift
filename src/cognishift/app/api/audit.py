from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status

from cognishift.app.db.database import get_db
from cognishift.app.db.models import AuditEventResponse
from cognishift.app.core.auth import get_current_user, verify_workspace_access, User

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])


@router.get("", response_model=List[AuditEventResponse])
async def list_audit_events(
    workspace_id: Optional[int] = Query(None, description="Filter by workspace ID"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    user: User = Depends(get_current_user),
):
    """Retrieve audit events ledger records with workspace access control."""
    if workspace_id is not None:
        verify_workspace_access(workspace_id, user)

    async with get_db() as db:
        if user.role == "administrator":
            if workspace_id is not None:
                cursor = await db.execute(
                    "SELECT * FROM audit_events WHERE workspace_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (workspace_id, limit, offset),
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM audit_events ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
        else:
            if workspace_id is not None:
                cursor = await db.execute(
                    "SELECT * FROM audit_events WHERE workspace_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (workspace_id, limit, offset),
                )
            else:
                placeholders = ",".join("?" for _ in user.allowed_workspace_ids)
                if not placeholders:
                    return []
                query = f"""
                    SELECT * FROM audit_events
                    WHERE workspace_id IN ({placeholders}) OR workspace_id IS NULL
                    ORDER BY created_at DESC LIMIT ? OFFSET ?
                """
                params = tuple(user.allowed_workspace_ids) + (limit, offset)
                cursor = await db.execute(query, params)

        rows = await cursor.fetchall()
        return [AuditEventResponse.model_validate(dict(row)) for row in rows]
