from fastapi import APIRouter, HTTPException, Query, Depends, status
from typing import List, Optional

from cognishift.app.db.database import get_db
from cognishift.app.db.models import RunCreate, RunResponse, RunEventResponse
from cognishift.app.core.auth import get_current_user, verify_workspace_access, User
from cognishift.core.engine import execute_agent_run, resume_agent_run

router = APIRouter(prefix="/api/v1/runs", tags=["Runs"])


@router.post("", response_model=RunResponse)
async def create_run(
    run_req: RunCreate,
    user: User = Depends(get_current_user)
):
    """Trigger a new agent reasoning run.
    
    P0-6 ENFORCEMENT:
    Requester identity strictly derives from the authenticated server-side user context.
    Any 'user_id' supplied inside the request body is discarded.
    """
    verify_workspace_access(run_req.workspace_id, user)
    try:
        run_res = await execute_agent_run(
            workspace_id=run_req.workspace_id,
            agent_id=run_req.agent_id,
            input_text=run_req.input_text or "",
            user_id=user.user_id,
            input_image_path=run_req.input_image_path
        )
        return run_res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Engine execution error: {str(e)}")


@router.get("", response_model=List[RunResponse])
async def list_runs(
    workspace_id: Optional[int] = Query(None, description="Filter runs by workspace"),
    agent_id: Optional[int] = Query(None, description="Filter runs by agent"),
    user: User = Depends(get_current_user)
):
    """List past agent runs authorized for current user."""
    async with get_db() as db:
        clauses = []
        params = []
        if workspace_id is not None:
            verify_workspace_access(workspace_id, user)
            clauses.append("workspace_id = ?")
            params.append(workspace_id)
        else:
            if user.role != "administrator":
                placeholders = ",".join("?" for _ in user.allowed_workspace_ids)
                if not placeholders:
                    return []
                clauses.append(f"workspace_id IN ({placeholders})")
                params.extend(user.allowed_workspace_ids)

        if agent_id is not None:
            clauses.append("agent_id = ?")
            params.append(agent_id)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM agent_runs {where_sql} ORDER BY started_at DESC"
        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        return [RunResponse.model_validate(dict(r)) for r in rows]


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: int,
    user: User = Depends(get_current_user)
):
    """Get status and result for a specific run with workspace access check."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")
        verify_workspace_access(row["workspace_id"], user)
        return RunResponse.model_validate(dict(row))


@router.get("/{run_id}/events", response_model=List[RunEventResponse])
async def get_run_events(
    run_id: int,
    user: User = Depends(get_current_user)
):
    """Get the event timeline for a run with workspace access check."""
    async with get_db() as db:
        cursor = await db.execute("SELECT workspace_id FROM agent_runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")
        verify_workspace_access(row["workspace_id"], user)

        cursor = await db.execute(
            "SELECT * FROM run_events WHERE run_id = ? ORDER BY created_at ASC, id ASC",
            (run_id,)
        )
        rows = await cursor.fetchall()
        return [RunEventResponse.model_validate(dict(r)) for r in rows]


@router.post("/{run_id}/resume", response_model=RunResponse)
async def resume_run(
    run_id: int,
    user: User = Depends(get_current_user)
):
    """Resume a paused run with supervisor verification."""
    if user.role not in ["supervisor", "administrator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: Role '{user.role}' cannot resume runs."
        )

    async with get_db() as db:
        cursor = await db.execute("SELECT workspace_id FROM agent_runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")
        verify_workspace_access(row["workspace_id"], user)

    try:
        run_res = await resume_agent_run(run_id=run_id)
        return run_res
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume run: {str(e)}")
