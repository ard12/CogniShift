from fastapi import APIRouter, HTTPException
from typing import List
from cognishift.app.db.database import get_db
from cognishift.app.db.models import WorkspaceCreate, WorkspaceResponse

router = APIRouter(prefix='/api/v1/workspaces', tags=['Workspaces'])

@router.post('', response_model=WorkspaceResponse)
async def create_workspace(workspace: WorkspaceCreate):
    """Create a new workspace."""
    async with get_db() as db:
        cursor = await db.execute(
            '''INSERT INTO workspaces (name, description, operating_mode)
               VALUES (?, ?, ?) RETURNING *''',
            (workspace.name, workspace.description, workspace.operating_mode)
        )
        row = await cursor.fetchone()
        await db.commit()
        return dict(row)

@router.get('', response_model=List[WorkspaceResponse])
async def list_workspaces():
    """List all workspaces."""
    async with get_db() as db:
        cursor = await db.execute('SELECT * FROM workspaces')
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

@router.get('/{workspace_id}', response_model=WorkspaceResponse)
async def get_workspace(workspace_id: int):
    """Get a specific workspace by ID."""
    async with get_db() as db:
        cursor = await db.execute('SELECT * FROM workspaces WHERE id = ?', (workspace_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Workspace not found')
        return dict(row)
