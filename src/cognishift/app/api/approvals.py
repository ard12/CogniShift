from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
from datetime import datetime, timezone

from cognishift.app.db.database import get_db
from cognishift.app.db.models import ApprovalResponse
from cognishift.app.core.auth import get_current_user, verify_four_eyes_approval, verify_workspace_access, User
from cognishift.core.engine import resume_agent_run

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])

@router.get("", response_model=List[ApprovalResponse])
async def list_pending_approvals(user: User = Depends(get_current_user)):
    """List pending approval requests authorized for the current user."""
    async with get_db() as db:
        if user.role == "administrator":
            cursor = await db.execute(
                "SELECT * FROM approval_requests WHERE status = 'pending' ORDER BY requested_at DESC"
            )
        else:
            placeholders = ",".join("?" for _ in user.allowed_workspace_ids)
            if not placeholders:
                return []
            cursor = await db.execute(
                f"""SELECT ar.* FROM approval_requests ar
                    JOIN agent_runs r ON ar.run_id = r.id
                    WHERE ar.status = 'pending' AND r.workspace_id IN ({placeholders})
                    ORDER BY ar.requested_at DESC""",
                tuple(user.allowed_workspace_ids)
            )
        rows = await cursor.fetchall()
        return [ApprovalResponse.model_validate(dict(row)) for row in rows]

@router.post("/{request_id}/approve", response_model=ApprovalResponse)
async def approve_request(
    request_id: int,
    approver: User = Depends(get_current_user)
):
    """Approve a paused tool request with Four-Eyes supervisor verification."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,))
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Approval request not found")
        if row["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Request is already {row['status']}")

        run_id = row["run_id"]
        # Fetch the original run to identify the requester and workspace
        cursor_run = await db.execute("SELECT user_id, workspace_id FROM agent_runs WHERE id = ?", (run_id,))
        run_row = await cursor_run.fetchone()
        if not run_row:
            raise HTTPException(status_code=404, detail="Associated agent run not found")
            
        verify_workspace_access(run_row["workspace_id"], approver)
        requester_id = run_row["user_id"] or "operator"

        # Enforce Four-Eyes Principle: requester != approver and approver is supervisor/admin
        verify_four_eyes_approval(requester_id=requester_id, approver=approver)
            
        now = datetime.now(timezone.utc).isoformat()
        cursor_update = await db.execute(
            """UPDATE approval_requests 
               SET status = 'approved', reviewed_by = ?, reviewed_at = ? 
               WHERE id = ? AND status = 'pending' RETURNING *""",
            (approver.user_id, now, request_id)
        )
        updated_row = await cursor_update.fetchone()
        if not updated_row:
            raise HTTPException(status_code=409, detail="Approval request was already resolved concurrently.")
        await db.commit()

    # Trigger engine resumption
    await resume_agent_run(run_id)
    
    return ApprovalResponse.model_validate(dict(updated_row))

@router.post("/{request_id}/reject", response_model=ApprovalResponse)
async def reject_request(
    request_id: int,
    approver: User = Depends(get_current_user)
):
    """Reject a paused tool request with Four-Eyes supervisor verification."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,))
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Approval request not found")
        if row["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Request is already {row['status']}")

        run_id = row["run_id"]
        cursor_run = await db.execute("SELECT user_id, workspace_id FROM agent_runs WHERE id = ?", (run_id,))
        run_row = await cursor_run.fetchone()
        if not run_row:
            raise HTTPException(status_code=404, detail="Associated agent run not found")
            
        verify_workspace_access(run_row["workspace_id"], approver)
        requester_id = run_row["user_id"] or "operator"

        verify_four_eyes_approval(requester_id=requester_id, approver=approver)

        now = datetime.now(timezone.utc).isoformat()
        cursor_update = await db.execute(
            """UPDATE approval_requests 
               SET status = 'rejected', reviewed_by = ?, reviewed_at = ? 
               WHERE id = ? AND status = 'pending' RETURNING *""",
            (approver.user_id, now, request_id)
        )
        updated_row = await cursor_update.fetchone()
        if not updated_row:
            raise HTTPException(status_code=409, detail="Approval request was already resolved concurrently.")
        await db.commit()

    # Trigger engine resumption
    await resume_agent_run(run_id)
    
    return ApprovalResponse.model_validate(dict(updated_row))
