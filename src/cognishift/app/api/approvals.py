from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime

from cognishift.app.db.database import get_db
from cognishift.app.db.models import ApprovalResponse

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
async def approve_request(request_id: int):
    """Approve a paused tool request."""
    async with get_db() as db:
        # Verify it exists and is pending
        cursor = await db.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,))
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Approval request not found")
        if row["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Request is already {row['status']}")
            
        # Update status
        now = datetime.utcnow()
        cursor = await db.execute(
            """UPDATE approval_requests 
               SET status = 'approved', reviewed_by = 'human_supervisor', reviewed_at = ? 
               WHERE id = ? RETURNING *""",
            (now, request_id)
        )
        updated_row = await cursor.fetchone()
        
        # Note: In Phase 5 (Sitanshu's Engine), the engine will poll or listen for this DB change to resume.
        
        await db.commit()
        return ApprovalResponse.model_validate(dict(updated_row))

@router.post("/{request_id}/reject", response_model=ApprovalResponse)
async def reject_request(request_id: int):
    """Reject a paused tool request."""
    async with get_db() as db:
        # Verify it exists and is pending
        cursor = await db.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,))
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Approval request not found")
        if row["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Request is already {row['status']}")
            
        # Update status
        now = datetime.utcnow()
        cursor = await db.execute(
            """UPDATE approval_requests 
               SET status = 'rejected', reviewed_by = 'human_supervisor', reviewed_at = ? 
               WHERE id = ? RETURNING *""",
            (now, request_id)
        )
        updated_row = await cursor.fetchone()
        await db.commit()
        return ApprovalResponse.model_validate(dict(updated_row))
