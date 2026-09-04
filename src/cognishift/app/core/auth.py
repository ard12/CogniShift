import os
import json
import hashlib
import secrets
import threading
import time
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
EPHEMERAL_DEMO_SESSIONS: Dict[str, tuple[User, float]] = {}
_CREDENTIAL_STORE_SIGNATURE: Optional[tuple[int, int]] = None
_CREDENTIAL_STORE_LOCK = threading.RLock()


def hash_token(raw_token: str) -> str:
    """Compute deterministic SHA-256 hash of raw authentication token."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def load_credential_store(store_path: Optional[Path] = None) -> int:
    """Load user credentials from external local configuration file."""
    global _CREDENTIAL_STORE_SIGNATURE
    path = store_path or getattr(settings, "auth_store_path", None)
    if not path or not Path(path).exists():
        return 0

    try:
        content = Path(path).read_text(encoding="utf-8")
        data = json.loads(content)
        records = [CredentialRecord.model_validate(u) for u in data.get("users", [])]
        with _CREDENTIAL_STORE_LOCK:
            LOCAL_CREDENTIAL_STORE.clear()
            LOCAL_CREDENTIAL_STORE.update({record.credential_hash: record for record in records})
            stat = Path(path).stat()
            _CREDENTIAL_STORE_SIGNATURE = (stat.st_mtime_ns, stat.st_size)
        return len(records)
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
    stat = p.stat()
    global _CREDENTIAL_STORE_SIGNATURE
    _CREDENTIAL_STORE_SIGNATURE = (stat.st_mtime_ns, stat.st_size)
    return True


def refresh_credential_store_if_changed() -> bool:
    """Atomically reload credentials when another process updates the configured store."""
    path = Path(settings.auth_store_path)
    if not path.exists():
        return False
    stat = path.stat()
    signature = (stat.st_mtime_ns, stat.st_size)
    if signature == _CREDENTIAL_STORE_SIGNATURE:
        return False
    load_credential_store(path)
    return True


def remove_credentials_for_users(user_ids: List[str]) -> int:
    """Remove persisted persona credentials before an explicit credential rotation."""
    normalized = {user_id.strip().lower() for user_id in user_ids}
    with _CREDENTIAL_STORE_LOCK:
        stale_hashes = [
            credential_hash
            for credential_hash, record in LOCAL_CREDENTIAL_STORE.items()
            if record.user_id.strip().lower() in normalized
        ]
        for credential_hash in stale_hashes:
            LOCAL_CREDENTIAL_STORE.pop(credential_hash, None)
    return len(stale_hashes)


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
    now = time.time()
    expired = [token_hash for token_hash, (_, expires_at) in EPHEMERAL_DEMO_SESSIONS.items() if expires_at <= now]
    for token_hash in expired:
        EPHEMERAL_DEMO_SESSIONS.pop(token_hash, None)

    demo_session = EPHEMERAL_DEMO_SESSIONS.get(incoming_hash)
    if demo_session:
        return demo_session[0].model_copy(deep=True)

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


def create_ephemeral_demo_session(user: User, ttl_seconds: Optional[int] = None) -> tuple[str, int]:
    """Create a random, process-local demo credential that is never written to disk."""
    ttl = max(60, min(ttl_seconds or settings.demo_session_ttl_seconds, 3600))
    raw_token = f"cog_demo_{secrets.token_urlsafe(32)}"
    EPHEMERAL_DEMO_SESSIONS[hash_token(raw_token)] = (user.model_copy(deep=True), time.time() + ttl)
    return raw_token, ttl


def clear_ephemeral_demo_sessions() -> None:
    EPHEMERAL_DEMO_SESSIONS.clear()


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
    query_token = request.query_params.get("token", "").strip()
    token = ""

    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif api_key:
        token = api_key
    elif query_token:
        token = query_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials. Provide a Bearer token or X-API-Key.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    refresh_credential_store_if_changed()
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
