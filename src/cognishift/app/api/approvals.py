from fastapi import APIRouter, HTTPException, Depends
from typing import List
from datetime import datetime

from cognishift.app.db.database import get_db
from cognishift.app.db.models import ApprovalResponse
from cognishift.app.core.auth import get_current_user, verify_four_eyes_approval, User
from cognishift.core.engine import resume_agent_run

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])

@router.get("", response_model=List[ApprovalResponse])
async def list_pending_approvals():
    """List all pending tool requests that require human approval."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM approval_requests WHERE status = 'pending' ORDER BY requested_at DESC"
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
        # Fetch the original run to identify the requester
        cursor_run = await db.execute("SELECT user_id FROM agent_runs WHERE id = ?", (run_id,))
        run_row = await cursor_run.fetchone()
        requester_id = run_row["user_id"] if run_row else "operator"

        # Enforce Four-Eyes Principle: requester != approver and approver is supervisor/admin
        verify_four_eyes_approval(requester_id=requester_id, approver=approver)
            
        now = datetime.utcnow().isoformat()
        cursor_update = await db.execute(
            """UPDATE approval_requests 
               SET status = 'approved', reviewed_by = ?, reviewed_at = ? 
               WHERE id = ? RETURNING *""",
            (approver.user_id, now, request_id)
        )
        updated_row = await cursor_update.fetchone()
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
        cursor_run = await db.execute("SELECT user_id FROM agent_runs WHERE id = ?", (run_id,))
        run_row = await cursor_run.fetchone()
        requester_id = run_row["user_id"] if run_row else "operator"

        # Enforce Four-Eyes Principle
        verify_four_eyes_approval(requester_id=requester_id, approver=approver)
            
        now = datetime.utcnow().isoformat()
        cursor_update = await db.execute(
            """UPDATE approval_requests 
               SET status = 'rejected', reviewed_by = ?, reviewed_at = ? 
               WHERE id = ? RETURNING *""",
            (approver.user_id, now, request_id)
        )
        updated_row = await cursor_update.fetchone()
        await db.commit()

    # Resume run to process rejection
    await resume_agent_run(run_id)
    
    return ApprovalResponse.model_validate(dict(updated_row))
