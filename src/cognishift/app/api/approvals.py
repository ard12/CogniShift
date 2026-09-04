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
        approval = dict(row)
        if approval["status"] != "pending":
            if approval["status"] == "approved":
                run_id = approval["run_id"]
                cursor_run = await db.execute("SELECT user_id, workspace_id, status FROM agent_runs WHERE id = ?", (run_id,))
                run_row = await cursor_run.fetchone()
                if run_row and run_row["status"] == "paused":
                    verify_workspace_access(run_row["workspace_id"], approver)
                    verify_four_eyes_approval(requester_id=run_row["user_id"] or "operator", approver=approver)
                    await resume_agent_run(run_id)
                    return ApprovalResponse.model_validate(approval)
            raise HTTPException(status_code=400, detail=f"Request is already {approval['status']}")

        run_id = approval["run_id"]
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
        required_approvals = approval.get("required_approvals") or 1

        if required_approvals == 2 and not approval.get("reviewed_by"):
            # Step 1 of 2: First supervisor approval recorded
            cursor_update = await db.execute(
                """UPDATE approval_requests 
                   SET reviewed_by = ?, reviewed_at = ? 
                   WHERE id = ? AND status = 'pending' RETURNING *""",
                (approver.user_id, now, request_id)
            )
            updated_row = await cursor_update.fetchone()
            if not updated_row:
                raise HTTPException(status_code=409, detail="Approval request was already resolved concurrently.")

            # Record audit event
            await db.execute(
                """INSERT INTO audit_events (workspace_id, actor_id, action, resource_type, resource_id, details, result)
                   VALUES (?, ?, 'approval_stage_1_verified', 'approval_request', ?, ?, 'success')""",
                (run_row["workspace_id"], approver.user_id, request_id, f"Four-Eyes Stage 1/2 verified by {approver.user_id}. Awaiting Stage 2 sign-off.")
            )
            await db.commit()
            return ApprovalResponse.model_validate(dict(updated_row))

        elif required_approvals == 2 and approval.get("reviewed_by"):
            # Step 2 of 2: Second independent approver must differ from First Approver
            first_approver = approval["reviewed_by"].lower().strip()
            if approver.user_id.lower().strip() == first_approver:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Four-Eyes Policy Violation: User '{approver.user_id}' already provided Stage 1 approval. "
                        "Stage 2 must be authorized by an independent, different supervisor or administrator."
                    )
                )

            cursor_update = await db.execute(
                """UPDATE approval_requests 
                   SET status = 'approved', reviewed_by_2 = ?, reviewed_at_2 = ? 
                   WHERE id = ? AND status = 'pending' RETURNING *""",
                (approver.user_id, now, request_id)
            )
            updated_row = await cursor_update.fetchone()
            if not updated_row:
                raise HTTPException(status_code=409, detail="Approval request was already resolved concurrently.")

            await db.execute(
                """INSERT INTO audit_events (workspace_id, actor_id, action, resource_type, resource_id, details, result)
                   VALUES (?, ?, 'approval_stage_2_authorized', 'approval_request', ?, ?, 'success')""",
                (run_row["workspace_id"], approver.user_id, request_id, f"Four-Eyes Stage 2/2 authorized by {approver.user_id}. Action approved.")
            )
            await db.commit()

        else:
            # Standard single supervisor approval (required_approvals == 1)
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

    # Trigger engine resumption when fully approved
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
