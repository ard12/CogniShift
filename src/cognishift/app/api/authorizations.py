"""REST APIs for Sovereign Temporary Operational Authorizations.

Domain prefix: /api/v1/authorizations
Provides authenticated, RBAC-enforced, and Four-Eyes verified endpoints for:
- Requesting temporary permits
- Dual supervisor approval (Stage 1 & Stage 2)
- Explicit administrator override
- Concurrency-safe atomic permit consumption
"""
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from cognishift.app.core.auth import (
    User,
    get_current_user,
    verify_workspace_access,
)
from cognishift.app.db.database import get_db
from cognishift.core.authorizations import (
    admin_override_authorization,
    approve_authorization_stage,
    execute_authorized_action_atomic,
    request_temporary_authorization,
    revoke_authorization,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/authorizations", tags=["Authorizations"])


class CreatePermitRequest(BaseModel):
    workspace_id: int = Field(default=1, description="Target workspace ID")
    action: str = Field(default="operate_pump", description="Target action or tool")
    resource: str = Field(default="P-101A", description="Target industrial asset")
    valid_duration_minutes: int = Field(default=60, ge=5, le=1440)
    target_user_id: Optional[str] = Field(None, description="Operator user ID (defaults to caller)")
    trusted_device_id: Optional[str] = Field(None, description="Optional device key binding")
    reason: Optional[str] = Field("One-time scheduled test run under supervisor authorization")


class AdminOverrideRequest(BaseModel):
    justification: str = Field(..., min_length=10, description="Mandatory administrative justification")


class RevokePermitRequest(BaseModel):
    reason: Optional[str] = Field("Revoked by supervisor", description="Reason for permit revocation")


class ExecutePermitRequest(BaseModel):
    permit_code: str = Field(..., description="Unique authorization permit code")
    action: str = Field(default="operate_pump", description="Authorized action to execute")
    resource: str = Field(default="P-101A", description="Authorized asset tag")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Execution parameters")


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/request", status_code=status.HTTP_201_CREATED)
async def create_permit_request(
    payload: CreatePermitRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Submit a new temporary authorization permit request (PENDING_APPROVAL 0/2)."""
    verify_workspace_access(payload.workspace_id, user)
    target_user = payload.target_user_id or user.user_id

    # If non-admin/supervisor attempts to request for another user, reject
    if target_user != user.user_id and user.role not in ("supervisor", "administrator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operators can only request authorization permits for their own user account.",
        )

    return await request_temporary_authorization(
        workspace_id=payload.workspace_id,
        user_id=target_user,
        action=payload.action,
        resource=payload.resource,
        valid_duration_minutes=payload.valid_duration_minutes,
        trusted_device_id=payload.trusted_device_id,
        requested_by=user.user_id,
        reason=payload.reason,
    )


@router.get("")
async def list_permits(
    workspace_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """List authorization permits scoped by caller role and workspace permissions."""
    async with get_db() as db:
        query_parts = ["SELECT * FROM temporary_authorizations WHERE 1=1"]
        params: List[Any] = []

        # Role-based scoping
        if user.role == "administrator":
            pass  # Admin can inspect all permits
        elif user.role == "supervisor":
            # Supervised workspaces
            if user.allowed_workspace_ids:
                ph = ",".join("?" for _ in user.allowed_workspace_ids)
                query_parts.append(f"AND workspace_id IN ({ph})")
                params.extend(user.allowed_workspace_ids)
            else:
                return {"permits": [], "total": 0}
        else:
            # Operator sees only permits issued to them
            query_parts.append("AND user_id = ?")
            params.append(user.user_id)

        if workspace_id is not None:
            verify_workspace_access(workspace_id, user)
            query_parts.append("AND workspace_id = ?")
            params.append(workspace_id)

        if status_filter:
            query_parts.append("AND status = ?")
            params.append(status_filter.upper())

        query_parts.append("ORDER BY id DESC")
        sql = " ".join(query_parts)

        rows = await (await db.execute(sql, tuple(params))).fetchall()
        permits = [dict(r) for r in rows]

        return {"permits": permits, "total": len(permits)}


@router.get("/{permit_id}")
async def get_permit_detail(
    permit_id: int,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve full permit record, status, audit history, and artifact link."""
    async with get_db() as db:
        row = await (await db.execute(
            "SELECT * FROM temporary_authorizations WHERE id = ?",
            (permit_id,),
        )).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Authorization permit not found.")

        permit = dict(row)
        verify_workspace_access(permit["workspace_id"], user)

        # Non-admin/supervisor can only inspect their own permits
        if user.role not in ("supervisor", "administrator") and permit["user_id"] != user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to other operators' authorization permits.",
            )

        # Audit events for this permit
        audits = await (await db.execute(
            "SELECT * FROM audit_events WHERE resource_type = 'temporary_authorization' AND resource_id = ? ORDER BY id ASC",
            (permit_id,),
        )).fetchall()
        permit["audit_events"] = [dict(a) for a in audits]

        # Artifact details if registered
        if permit.get("artifact_id"):
            art = await (await db.execute(
                "SELECT * FROM workspace_artifacts WHERE id = ?",
                (permit["artifact_id"],),
            )).fetchone()
            permit["artifact"] = dict(art) if art else None

        return permit


@router.post("/{permit_id}/approve")
async def approve_permit(
    permit_id: int,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Execute supervisor Four-Eyes approval stage (Stage 1 or Stage 2)."""
    async with get_db() as db:
        row = await (await db.execute("SELECT workspace_id FROM temporary_authorizations WHERE id = ?", (permit_id,))).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Authorization permit not found.")
        verify_workspace_access(row["workspace_id"], user)
    return await approve_authorization_stage(
        permit_id=permit_id,
        approver_id=user.user_id,
        approver_role=user.role,
    )


@router.post("/{permit_id}/admin-override")
async def override_permit(
    permit_id: int,
    payload: AdminOverrideRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Explicit administrator override for authorization permit."""
    async with get_db() as db:
        row = await (await db.execute("SELECT workspace_id FROM temporary_authorizations WHERE id = ?", (permit_id,))).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Authorization permit not found.")
        verify_workspace_access(row["workspace_id"], user)
    return await admin_override_authorization(
        permit_id=permit_id,
        admin_id=user.user_id,
        admin_role=user.role,
        justification=payload.justification,
    )


@router.post("/{permit_id}/revoke")
async def revoke_permit(
    permit_id: int,
    payload: RevokePermitRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Revoke an active or pending authorization permit."""
    async with get_db() as db:
        row = await (await db.execute("SELECT workspace_id FROM temporary_authorizations WHERE id = ?", (permit_id,))).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Authorization permit not found.")
        verify_workspace_access(row["workspace_id"], user)
    return await revoke_authorization(
        permit_id=permit_id,
        caller_id=user.user_id,
        caller_role=user.role,
        reason=payload.reason,
    )


@router.post("/execute")
async def execute_permit(
    payload: ExecutePermitRequest,
    request: Request,
    user: User = Depends(get_current_user),
    x_device_id: Optional[str] = Header(None, alias="X-Device-ID"),
) -> Dict[str, Any]:
    """Atomically consume one-time permit and execute simulated industrial action.
    
    Adheres strictly to atomic CAS concurrency enforcement:
    First simultaneous execution consumes permit; second execution fails with 403 AUTHORIZATION_CONSUMED.
    """
    caller_device_id = x_device_id or getattr(request.state, "device_id", None)
    return await execute_authorized_action_atomic(
        permit_code=payload.permit_code.strip(),
        caller_user_id=user.user_id,
        action=payload.action.strip(),
        resource=payload.resource.strip(),
        caller_device_id=caller_device_id,
        parameters=payload.parameters,
    )

