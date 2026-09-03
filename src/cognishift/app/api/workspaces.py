from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
from cognishift.app.db.database import get_db
from cognishift.app.db.models import WorkspaceCreate, WorkspaceResponse
from cognishift.app.core.auth import get_current_user, verify_workspace_access, User

router = APIRouter(prefix='/api/v1/workspaces', tags=['Workspaces'])

@router.post('', response_model=WorkspaceResponse)
async def create_workspace(
    workspace: WorkspaceCreate,
    user: User = Depends(get_current_user)
):
    """Create a new workspace (requires supervisor or administrator role)."""
    if user.role not in ["supervisor", "administrator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: Role '{user.role}' cannot create workspaces."
        )

    async with get_db() as db:
        cursor = await db.execute(
            '''INSERT INTO workspaces (name, description, operating_mode)
               VALUES (?, ?, ?) RETURNING *''',
            (workspace.name, workspace.description, workspace.operating_mode)
        )
        row = await cursor.fetchone()
        await db.commit()
        from cognishift.core.security import ensure_workspace_layout
        ensure_workspace_layout(row["id"])
        return dict(row)

@router.get('', response_model=List[WorkspaceResponse])
async def list_workspaces(user: User = Depends(get_current_user)):
    """List workspaces authorized for the current user."""
    async with get_db() as db:
        if user.role == "administrator":
            cursor = await db.execute('SELECT * FROM workspaces')
            rows = await cursor.fetchall()
        else:
            placeholders = ",".join("?" for _ in user.allowed_workspace_ids)
            if not placeholders:
                return []
            cursor = await db.execute(
                f'SELECT * FROM workspaces WHERE id IN ({placeholders})',
                tuple(user.allowed_workspace_ids)
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

@router.get('/{workspace_id}', response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: int,
    user: User = Depends(get_current_user)
):
    """Get a specific workspace by ID with tenant authorization check."""
    verify_workspace_access(workspace_id, user)
    async with get_db() as db:
        cursor = await db.execute('SELECT * FROM workspaces WHERE id = ?', (workspace_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Workspace not found')
        return dict(row)
