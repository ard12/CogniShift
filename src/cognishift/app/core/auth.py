import os
import json
import hashlib
import secrets
from pathlib import Path
from typing import Optional, List, Literal, Dict
from fastapi import Request, HTTPException, Security, status
from pydantic import BaseModel, Field

from cognishift.app.config import settings

UserRole = Literal["operator", "supervisor", "administrator"]


class User(BaseModel):
    """Authenticated user context derived exclusively from verified server credentials."""
    user_id: str
    role: UserRole = "operator"
    allowed_workspace_ids: List[int] = Field(default_factory=lambda: [1])


class CredentialRecord(BaseModel):
    """Secure credential entry storing only cryptographic hashes and authorization scopes."""
    credential_hash: str
    user_id: str
    role: UserRole
    allowed_workspace_ids: List[int] = Field(default_factory=lambda: [1])
    enabled: bool = True


# -----------------------------------------------------------------------------
# SERVER-SIDE LOCAL CREDENTIAL STORE (Zero Cloud / Cryptographically Verified)
# -----------------------------------------------------------------------------
LOCAL_CREDENTIAL_STORE: Dict[str, CredentialRecord] = {}


def hash_token(raw_token: str) -> str:
    """Compute deterministic SHA-256 hash of raw authentication token."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def load_credential_store(store_path: Optional[Path] = None) -> int:
    """Load user credentials from external local configuration file."""
    global LOCAL_CREDENTIAL_STORE
    path = store_path or getattr(settings, "auth_store_path", None)
    if not path or not Path(path).exists():
        return 0

    try:
        content = Path(path).read_text(encoding="utf-8")
        data = json.loads(content)
        users = data.get("users", [])
        loaded = 0
        for u in users:
            record = CredentialRecord.model_validate(u)
            LOCAL_CREDENTIAL_STORE[record.credential_hash] = record
            loaded += 1
        return loaded
    except Exception:
        return 0


def save_credential_store(store_path: Optional[Path] = None) -> bool:
    """Persist the current credential store to an uncommitted local JSON file."""
    path = store_path or getattr(settings, "auth_store_path", None)
    if not path:
        return False

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "$comment": "CogniShift Local Sovereign Credential Store. Excluded from Git.",
        "users": [rec.model_dump() for rec in LOCAL_CREDENTIAL_STORE.values()]
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return True


def register_local_credential(raw_token: str, user: User, enabled: bool = True) -> str:
    """Register or update a local credential. Stores only the SHA-256 hash."""
    c_hash = hash_token(raw_token)
    record = CredentialRecord(
        credential_hash=c_hash,
        user_id=user.user_id,
        role=user.role,
        allowed_workspace_ids=user.allowed_workspace_ids,
        enabled=enabled
    )
    LOCAL_CREDENTIAL_STORE[c_hash] = record
    return c_hash


def authenticate_token(raw_token: str) -> Optional[User]:
    """Verify raw token against stored cryptographic hashes using constant-time comparison."""
    if not raw_token:
        return None
    incoming_hash = hash_token(raw_token)
    for stored_hash, record in LOCAL_CREDENTIAL_STORE.items():
        if secrets.compare_digest(stored_hash, incoming_hash):
            if not record.enabled:
                return None
            return User(
                user_id=record.user_id,
                role=record.role,
                allowed_workspace_ids=record.allowed_workspace_ids
            )
    return None


# Initial load from local config if available
load_credential_store()


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

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials. Provide a Bearer token or X-API-Key.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = authenticate_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unrecognized authentication token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user


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
