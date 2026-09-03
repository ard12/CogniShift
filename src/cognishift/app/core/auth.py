"""Role-Based Access Control and Verified Local Authentication for CogniShift."""
from typing import Optional, List, Literal, Dict
from fastapi import Request, HTTPException, Security, status
from pydantic import BaseModel, Field

UserRole = Literal["operator", "supervisor", "administrator"]


class User(BaseModel):
    """Authenticated user context derived exclusively from verified server credentials."""
    user_id: str
    role: UserRole = "operator"
    allowed_workspace_ids: List[int] = Field(default_factory=lambda: [1])


# -----------------------------------------------------------------------------
# SERVER-SIDE LOCAL CREDENTIAL STORE (Zero Cloud / Sovereign Verification)
# -----------------------------------------------------------------------------
LOCAL_CREDENTIAL_STORE: Dict[str, User] = {
    "token-operator-01": User(
        user_id="operator_sam",
        role="operator",
        allowed_workspace_ids=[1]
    ),
    "token-supervisor-01": User(
        user_id="supervisor_jane",
        role="supervisor",
        allowed_workspace_ids=[1, 2]
    ),
    "token-admin-01": User(
        user_id="admin_rohit",
        role="administrator",
        allowed_workspace_ids=[1, 2, 3]
    ),
    "token-tenant2-operator": User(
        user_id="operator_tenant2",
        role="operator",
        allowed_workspace_ids=[2]
    )
}


def register_local_credential(token: str, user: User) -> None:
    """Register or update a local credential in the server-side store."""
    LOCAL_CREDENTIAL_STORE[token] = user


async def get_current_user(request: Request) -> User:
    """
    Verify caller credentials against the server-side credential store.
    Extracts Bearer token from 'Authorization' header or 'X-API-Key' header.
    
    CRITICAL SECURITY GUARANTEE:
    Client-supplied headers (X-User-Role, X-User-ID) are NEVER trusted.
    Role and workspace permissions originate strictly from verified server records.
    """
    auth_header = request.headers.get("Authorization", "").strip()
    api_key = request.headers.get("X-API-Key", "").strip()
    token = ""

    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif api_key:
        token = api_key

    if not token or token not in LOCAL_CREDENTIAL_STORE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication credentials. Provide a valid Bearer token or X-API-Key.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return LOCAL_CREDENTIAL_STORE[token]


def verify_workspace_access(workspace_id: int, user: User) -> None:
    """
    Verify caller has permission to access the specified workspace.
    Raises HTTPException(403) on IDOR / unauthorized tenant access attempts.
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
    Both identities originate strictly from server-verified credentials.
    
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
