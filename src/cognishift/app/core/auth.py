"""Role-Based Access Control and Four-Eyes Identity Verification."""
from typing import Optional, List, Literal
from fastapi import Request, HTTPException, Security, status
from pydantic import BaseModel, Field

UserRole = Literal["operator", "supervisor", "administrator"]


class User(BaseModel):
    """Authenticated user context."""
    user_id: str
    role: UserRole = "operator"
    allowed_workspace_ids: List[int] = Field(default_factory=lambda: [1])


async def get_current_user(request: Request) -> User:
    """
    Extract authenticated user context from request headers.
    Defaults to operator in local mode for backward compatibility while enforcing identity.
    """
    user_id = request.headers.get("X-User-ID", "operator")
    role = request.headers.get("X-User-Role", "operator").lower()
    
    if role not in ["operator", "supervisor", "administrator"]:
        role = "operator"
        
    # In full enterprise deployment, workspace assignments come from identity provider.
    # Default to workspace 1 allowed for standard demo.
    allowed_ws_raw = request.headers.get("X-Allowed-Workspaces", "1")
    try:
        allowed_workspaces = [int(w.strip()) for w in allowed_ws_raw.split(",") if w.strip()]
    except ValueError:
        allowed_workspaces = [1]
        
    return User(user_id=user_id, role=role, allowed_workspace_ids=allowed_workspaces)


def verify_workspace_access(workspace_id: int, user: User) -> None:
    """
    Verify caller has permission to access the specified workspace.
    Raises HTTPException(403) on IDOR / unauthorized access attempts.
    """
    if user.role == "administrator":
        return
        
    if workspace_id not in user.allowed_workspace_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: User '{user.user_id}' is not authorized for Workspace #{workspace_id}."
        )


def verify_four_eyes_approval(requester_id: str, approver: User) -> None:
    """
    Enforces the strict Four-Eyes Principal on high-risk approvals:
    1. Requester cannot approve their own request (requester != approver).
    2. Approver must hold 'supervisor' or 'administrator' role.
    
    Raises HTTPException(403) on policy violations.
    """
    # Rule 1: Separation of Requester and Approver
    if approver.user_id.lower().strip() == requester_id.lower().strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Four-Eyes Policy Violation: Requester '{requester_id}' cannot approve their own request. "
                "Independent supervisor sign-off is mandatory."
            )
        )
        
    # Rule 2: Minimum Role Requirement
    if approver.role not in ["supervisor", "administrator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Four-Eyes Policy Violation: User '{approver.user_id}' has role '{approver.role}'. "
                "Only 'supervisor' or 'administrator' can authorize high-risk actions."
            )
        )
