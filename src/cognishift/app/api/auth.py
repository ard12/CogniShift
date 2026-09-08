import ipaddress
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from cognishift.app.config import settings
from cognishift.app.core.auth import User, authenticate_token, create_ephemeral_demo_session, get_current_user, refresh_credential_store_if_changed
from cognishift.app.core.device_security import begin_challenge, verify_challenge

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class UserProfileResponse(BaseModel):
    user_id: str
    role: str
    allowed_workspace_ids: List[int]


class DemoPersonaResponse(BaseModel):
    persona_id: str
    display_name: str
    role: str


class DemoModeResponse(BaseModel):
    enabled: bool
    session_ttl_seconds: int


class DemoSessionRequest(BaseModel):
    persona_id: str


class DemoSessionResponse(BaseModel):
    session_token: str
    expires_in_seconds: int


class DeviceChallengeRequest(BaseModel):
    device_id: str
    display_name: str = "Local browser"
    public_key_jwk: Dict[str, Any]


class DeviceChallengeResponse(BaseModel):
    status: str
    challenge_id: str
    challenge: str


class DeviceVerifyRequest(BaseModel):
    device_id: str
    challenge_id: str
    signature: str


class DeviceVerifyResponse(BaseModel):
    device_session: str
    expires_in_seconds: int
    device_status: str = "trusted"


DEMO_PERSONAS = {
    "operator": User(user_id="operator_sam", role="operator", allowed_workspace_ids=[1]),
    "supervisor": User(user_id="supervisor_jane", role="supervisor", allowed_workspace_ids=[1, 2]),
    "administrator": User(user_id="admin_rohit", role="administrator", allowed_workspace_ids=[1, 2, 3]),
}


def _is_loopback(request: Request) -> bool:
    host = request.client.host if request.client else ""
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


def _demo_mode_enabled() -> bool:
    return settings.cognishift_demo_mode and settings.operating_mode.lower() == "local"


def _credential_user(request: Request) -> User:
    auth_header = request.headers.get("Authorization", "").strip()
    token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else request.headers.get("X-API-Key", "").strip()
    refresh_credential_store_if_changed()
    user = authenticate_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or unrecognized authentication token.")
    return user


@router.post("/device/challenge", response_model=DeviceChallengeResponse)
async def create_device_challenge(payload: DeviceChallengeRequest, request: Request):
    """Verify credentials, then challenge an approved browser-held public key."""
    user = _credential_user(request)
    client_ip = request.client.host if request.client else None
    result = await begin_challenge(
        user.user_id,
        user.role,
        payload.device_id,
        payload.display_name,
        payload.public_key_jwk,
        is_loopback=_is_loopback(request),
        client_ip=client_ip,
    )
    if result["status"] != "challenge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "UNKNOWN_DEVICE",
                "title": "⚠ Unknown Device",
                "credentials": "Credentials Verified",
                "device": "Device Verification Failed",
                "action": "Administrator Approval Required",
                "device_status": result.get("status", "unknown_device"),
            },
        )
    return DeviceChallengeResponse(**result)


@router.post("/device/verify", response_model=DeviceVerifyResponse)
async def complete_device_challenge(payload: DeviceVerifyRequest, request: Request):
    user = _credential_user(request)
    try:
        session = await verify_challenge(user.user_id, payload.device_id, payload.challenge_id, payload.signature)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return DeviceVerifyResponse(device_session=session, expires_in_seconds=settings.device_session_ttl_seconds)


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(user: User = Depends(get_current_user)):
    """Return the authenticated caller's profile context."""
    return UserProfileResponse(
        user_id=user.user_id,
        role=user.role,
        allowed_workspace_ids=user.allowed_workspace_ids,
    )


@router.get("/demo-personas", response_model=List[DemoPersonaResponse])
async def list_demo_personas():
    """Return persona metadata only; credentials are never included."""
    return [
        DemoPersonaResponse(persona_id="operator", display_name="Sam (Field Operator)", role="operator"),
        DemoPersonaResponse(persona_id="supervisor", display_name="Jane (Plant Supervisor)", role="supervisor"),
        DemoPersonaResponse(persona_id="administrator", display_name="Rohit (System Authorizer)", role="administrator"),
    ]


@router.get("/demo-status", response_model=DemoModeResponse)
async def get_demo_status(request: Request):
    """Advertise demo convenience login only to a loopback browser."""
    enabled = _demo_mode_enabled() and _is_loopback(request)
    return DemoModeResponse(
        enabled=enabled,
        session_ttl_seconds=settings.demo_session_ttl_seconds if enabled else 0,
    )


@router.post("/demo-session", response_model=DemoSessionResponse)
async def create_demo_session(payload: DemoSessionRequest, request: Request):
    """Issue a short-lived process-local credential for a selected local persona."""
    if not _demo_mode_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Local demo authentication is disabled.")
    if not _is_loopback(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Local demo authentication is restricted to loopback clients.",
        )

    user = DEMO_PERSONAS.get(payload.persona_id.strip().lower())
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown local demo persona.")

    session_token, ttl = create_ephemeral_demo_session(user)
    return DemoSessionResponse(session_token=session_token, expires_in_seconds=ttl)
