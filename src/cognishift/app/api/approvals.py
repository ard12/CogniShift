import logging
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from cognishift.app.db.database import get_db
from cognishift.app.db.models import ApprovalResponse
from cognishift.app.core.auth import get_current_user, verify_four_eyes_approval, verify_workspace_access, User
from cognishift.core.engine import resume_agent_run

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])


class ApprovalDecisionRequest(BaseModel):
    decision: str = "approved"
    comment: Optional[str] = None


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


@router.get("/pending", response_model=List[ApprovalResponse])
async def list_pending_approvals_alias(user: User = Depends(get_current_user)):
    """Alias for /api/v1/approvals for backwards compatibility."""
    return await list_pending_approvals(user=user)


@router.post("/{request_id}/approve", response_model=ApprovalResponse)
async def approve_request(
    request_id: int,
    body: Optional[ApprovalDecisionRequest] = None,
    approver: User = Depends(get_current_user)
):
    """Approve a paused tool request with Four-Eyes supervisor verification."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,))
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Approval request not found")
        approval = dict(row)
        should_resume_early = False
        if approval["status"] != "pending":
            if approval["status"] == "approved":
                run_id = approval["run_id"]
                cursor_run = await db.execute("SELECT user_id, workspace_id, status FROM agent_runs WHERE id = ?", (run_id,))
                run_row = await cursor_run.fetchone()
                if run_row and run_row["status"] == "paused":
                    verify_workspace_access(run_row["workspace_id"], approver)
                    verify_four_eyes_approval(requester_id=run_row["user_id"] or "operator", approver=approver)
                    should_resume_early = True
            if not should_resume_early:
                raise HTTPException(status_code=400, detail=f"Request is already {approval['status']}")

        run_id = approval["run_id"]
        updated_row = None
        if not should_resume_early:
            # Fetch the original run to identify the requester and workspace
            cursor_run = await db.execute("SELECT user_id, workspace_id FROM agent_runs WHERE id = ?", (run_id,))
            run_row = await cursor_run.fetchone()
            if not run_row:
                raise HTTPException(status_code=404, detail="Associated agent run not found")
                
            verify_workspace_access(run_row["workspace_id"], approver)
            requester_id = run_row["user_id"] or "operator"

            # Enforce Four-Eyes Principle: requester != approver and approver is supervisor/admin
            verify_four_eyes_approval(requester_id=requester_id, approver=approver)
            
        if not should_resume_early:
            now = datetime.now(timezone.utc).isoformat()
            required_approvals = approval.get("required_approvals") or 1

            if required_approvals == 2 and not approval.get("reviewed_by"):
                cursor_update = await db.execute(
                    """UPDATE approval_requests 
                       SET reviewed_by = ?, reviewed_at = ? 
                       WHERE id = ? AND status = 'pending' AND reviewed_by IS NULL RETURNING *""",
                    (approver.user_id, now, request_id)
                )
                updated_row = await cursor_update.fetchone()
                if not updated_row:
                    raise HTTPException(status_code=409, detail="Approval request was already resolved concurrently.")

                # Record audit event
                audit_cur = await db.execute(
                    """INSERT INTO audit_events (workspace_id, actor_id, action, resource_type, resource_id, details, result)
                       VALUES (?, ?, 'approval_stage_1_verified', 'approval_request', ?, ?, 'success')""",
                    (run_row["workspace_id"], approver.user_id, request_id, f"Four-Eyes Stage 1/2 verified by {approver.user_id}. Awaiting Stage 2 sign-off.")
                )
                audit_id = audit_cur.lastrowid
                await db.commit()

                try:
                    from cognishift.core.notifications import (
                        NotificationType,
                        collect_four_eyes_evidence,
                        fire_and_forget_notification,
                    )
                    tool_r = await (await db.execute("SELECT name FROM tool_definitions WHERE id = ?", (approval["tool_id"],))).fetchone()
                    tool_n = tool_r["name"] if tool_r else "Tool"
                    fe_ev = collect_four_eyes_evidence(
                        event_type=NotificationType.FIRST_SUPERVISOR_APPROVAL,
                        run_id=run_id,
                        approval_id=request_id,
                        tool_name=tool_n,
                        parameters={},
                        user_id=run_row["user_id"] or "operator",
                        workspace_id=run_row["workspace_id"],
                        supervisor_1=approver.user_id,
                        audit_event_id=audit_id,
                    )
                    fire_and_forget_notification(fe_ev)
                except Exception:
                    pass

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
                       WHERE id = ? AND status = 'pending' AND reviewed_by = ?
                       AND reviewed_by_2 IS NULL RETURNING *""",
                    (approver.user_id, now, request_id, approval["reviewed_by"])
                )
                updated_row = await cursor_update.fetchone()
                if not updated_row:
                    raise HTTPException(status_code=409, detail="Approval request was already resolved concurrently.")

                audit_cur = await db.execute(
                    """INSERT INTO audit_events (workspace_id, actor_id, action, resource_type, resource_id, details, result)
                       VALUES (?, ?, 'approval_stage_2_authorized', 'approval_request', ?, ?, 'success')""",
                    (run_row["workspace_id"], approver.user_id, request_id, f"Four-Eyes Stage 2/2 authorized by {approver.user_id}. Action approved.")
                )
                audit_id = audit_cur.lastrowid
                await db.commit()

                try:
                    from cognishift.core.notifications import (
                        NotificationType,
                        collect_four_eyes_evidence,
                        fire_and_forget_notification,
                    )
                    tool_r = await (await db.execute("SELECT name FROM tool_definitions WHERE id = ?", (approval["tool_id"],))).fetchone()
                    tool_n = tool_r["name"] if tool_r else "Tool"
                    fe_ev = collect_four_eyes_evidence(
                        event_type=NotificationType.FOUR_EYES_COMPLETED,
                        run_id=run_id,
                        approval_id=request_id,
                        tool_name=tool_n,
                        parameters={},
                        user_id=run_row["user_id"] or "operator",
                        workspace_id=run_row["workspace_id"],
                        supervisor_1=approval["reviewed_by"],
                        supervisor_2=approver.user_id,
                        audit_event_id=audit_id,
                    )
                    fire_and_forget_notification(fe_ev)
                except Exception:
                    pass

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


    if should_resume_early:
        try:
            await resume_agent_run(run_id)
        except Exception as e:
            logger.error(f"Failed to resume agent run {run_id} after early approval: {e}", exc_info=True)
        return ApprovalResponse.model_validate(approval)

    # Trigger engine resumption when fully approved
    try:
        await resume_agent_run(run_id)
    except Exception as e:
        logger.error(f"Failed to resume agent run {run_id} after approval: {e}", exc_info=True)
    
    return ApprovalResponse.model_validate(dict(updated_row))

@router.post("/{request_id}/reject", response_model=ApprovalResponse)
async def reject_request(
    request_id: int,
    body: Optional[ApprovalDecisionRequest] = None,
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
    try:
        await resume_agent_run(run_id)
    except Exception as e:
        logger.error(f"Failed to resume agent run {run_id} after rejection: {e}", exc_info=True)
    
    return ApprovalResponse.model_validate(dict(updated_row))


@router.post("/{request_id}/review", response_model=ApprovalResponse)
async def review_request(
    request_id: int,
    body: Optional[ApprovalDecisionRequest] = None,
    approver: User = Depends(get_current_user)
):
    """Review an approval request with decision ('approved' or 'rejected')."""
    decision = (body.decision.lower().strip() if body and body.decision else "approved")
    if decision in ["approve", "approved"]:
        return await approve_request(request_id=request_id, body=body, approver=approver)
    elif decision in ["reject", "rejected"]:
        return await reject_request(request_id=request_id, body=body, approver=approver)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decision '{decision}'. Must be 'approved' or 'rejected'."
        )
