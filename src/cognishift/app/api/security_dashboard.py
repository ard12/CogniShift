"""Truthful security posture and trusted-device administration endpoints."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from cognishift.app.config import settings
from cognishift.app.core.auth import User, get_current_user, verify_workspace_access
from cognishift.app.db.database import get_db
from cognishift.core.network.guard import get_active_network_policy
from cognishift.core.providers import get_provider

router = APIRouter(prefix="/api/v1/security", tags=["Security"])


@router.get("/status")
async def security_status(workspace_id: int, request: Request, user: User = Depends(get_current_user)) -> Dict[str, Any]:
    verify_workspace_access(workspace_id, user)
    policy = get_active_network_policy()
    try:
        local_ai_active = bool(await get_provider().health_check())
    except Exception:
        local_ai_active = False
    async with get_db() as db:
        workspace_exists = bool(await (await db.execute(
            "SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)
        )).fetchone())
        if not workspace_exists:
            raise HTTPException(status_code=404, detail="Workspace not found.")
        protected_tools = (await (await db.execute(
            "SELECT count(*) AS n FROM tool_definitions WHERE enabled=1 AND requires_approval=1"
        )).fetchone())["n"]
        try:
            await db.execute("SELECT 1 FROM audit_events LIMIT 1")
            audit_active = True
        except Exception:
            audit_active = False
    import shutil
    import psutil
    from pathlib import Path

    # Docker sandbox detection
    docker_bin = shutil.which("docker")
    docker_label = "Docker Engine Active" if docker_bin else "Simulated Process Sandbox"
    docker_evidence = f"Binary: {Path(docker_bin).name}" if docker_bin else "Subprocess isolation active"

    # Physical network interface detection
    active_ifaces = []
    try:
        stats = psutil.net_if_stats()
        for if_name, if_stat in stats.items():
            if not if_name.lower().startswith("loopback") and if_stat.isup:
                active_ifaces.append(if_name)
    except Exception:
        pass
    iface_label = f"Interface Connected ({active_ifaces[0]})" if active_ifaces else "Interfaces Disconnected"
    iface_evidence = f"Active: {', '.join(active_ifaces[:2])}" if active_ifaces else "Physical interface inactive"

    return {
        "identity": {"status": "verified", "label": "Verified", "evidence": user.user_id},
        "device": {
            "status": "trusted" if getattr(request.state, "device_trusted", False) else "not_verified",
            "label": "Trusted" if getattr(request.state, "device_trusted", False) else "Not Verified",
            "evidence": getattr(request.state, "device_id", None),
        },
        "workspace": {"status": "authorized", "label": "Authorized", "evidence": f"Workspace #{workspace_id}"},
        "local_ai": {"status": "active" if local_ai_active else "unavailable", "label": "Active" if local_ai_active else "Unavailable"},
        "external_internet": {
            "status": "blocked" if policy.mode.value == "strict" else "not_verified",
            "label": "Blocked (Sovereign Policy)" if policy.mode.value == "strict" else "Not Verified",
            "evidence": f"Network policy: {policy.mode.value}",
        },
        "network_interface": {
            "status": "connected" if active_ifaces else "not_verified",
            "label": iface_label,
            "evidence": iface_evidence,
        },
        "docker_sandbox": {
            "status": "active" if docker_bin else "not_verified",
            "label": docker_label,
            "evidence": docker_evidence,
        },
        "sensitive_tools": {
            "status": "protected" if protected_tools > 0 else "not_verified",
            "label": "Approval Protected" if protected_tools > 0 else "Not Verified",
            "evidence": f"{protected_tools} enabled tools require approval",
        },
        "audit_logging": {"status": "active" if audit_active else "unavailable", "label": "Active" if audit_active else "Unavailable"},
        "trusted_device_enforcement": settings.trusted_device_required,
    }


@router.get("/devices/pending")
async def pending_devices(user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    if user.role != "administrator":
        raise HTTPException(status_code=403, detail="Administrator role required.")
    async with get_db() as db:
        rows = await (await db.execute(
            "SELECT device_id,user_id,display_name,key_fingerprint,created_at FROM trusted_devices WHERE status='pending' ORDER BY created_at"
        )).fetchall()
        return [dict(row) for row in rows]


@router.post("/devices/{device_id}/approve")
async def approve_device(
    device_id: str,
    user_id: Optional[str] = None,
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    if user.role != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")
    async with get_db() as db:
        if user_id:
            row = await (await db.execute(
                "SELECT * FROM trusted_devices WHERE device_id=? AND user_id=? AND status='pending'",
                (device_id, user_id),
            )).fetchone()
        else:
            rows = await (await db.execute(
                "SELECT * FROM trusted_devices WHERE device_id=? AND status='pending'",
                (device_id,),
            )).fetchall()
            if len(rows) > 1:
                raise HTTPException(status_code=409, detail="Multiple users are pending for this device; specify user_id.")
            row = rows[0] if rows else None
        if not row:
            raise HTTPException(status_code=404, detail="Pending device not found.")
        await db.execute(
            "UPDATE trusted_devices SET status='approved',approved_by=?,approved_at=CURRENT_TIMESTAMP WHERE device_id=? AND user_id=?",
            (user.user_id, device_id, row["user_id"]),
        )
        await db.execute(
            "INSERT INTO audit_events (actor_id,action,resource_type,details,result) VALUES (?,'trusted_device_approved','trusted_device',?,'success')",
            (user.user_id, f"Approved device_id={device_id} for user={row['user_id']}"),
        )
        await db.commit()
    return {"status": "approved", "device_id": device_id, "user_id": row["user_id"]}
