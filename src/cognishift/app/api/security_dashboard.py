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
    from cognishift.app.core.device_security import (
        approve_device as ds_approve_device,
        revoke_device as ds_revoke_device,
        block_device as ds_block_device,
    )

    # Docker sandbox detection
    docker_bin = shutil.which(settings.sandbox_runtime) or shutil.which("docker")
    if docker_bin:
        docker_status = "active"
        docker_label = "Docker Engine Active"
        docker_evidence = f"Binary: {Path(docker_bin).name}"
    elif settings.operating_mode == "simulated" or settings.sandbox_runtime == "simulated":
        docker_status = "active"
        docker_label = "Simulated Process Sandbox"
        docker_evidence = "Subprocess isolation / test mode active"
    else:
        docker_status = "unavailable"
        docker_label = "Container Sandbox Unavailable"
        docker_evidence = f"Runtime '{settings.sandbox_runtime}' not found on host"

    # Physical network interface detection
    active_ifaces = []
    iface_error = False
    try:
        stats = psutil.net_if_stats()
        for if_name, if_stat in stats.items():
            if not if_name.lower().startswith("loopback") and if_stat.isup:
                active_ifaces.append(if_name)
    except Exception:
        iface_error = True

    if iface_error:
        iface_status = "unknown"
        iface_label = "Interface Status Unknown"
        iface_evidence = "Interface inspection failed"
    elif active_ifaces:
        iface_status = "connected"
        iface_label = f"Interface Connected ({active_ifaces[0]})"
        iface_evidence = f"Active: {', '.join(active_ifaces[:2])}"
    else:
        iface_status = "disconnected"
        iface_label = "Interfaces Disconnected"
        iface_evidence = "Physical interface inactive"

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
            "status": iface_status,
            "label": iface_label,
            "evidence": iface_evidence,
        },
        "docker_sandbox": {
            "status": docker_status,
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


@router.get("/devices")
async def list_all_devices(user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    if user.role != "administrator":
        raise HTTPException(status_code=403, detail="Administrator role required.")
    async with get_db() as db:
        rows = await (await db.execute(
            "SELECT id, device_id, user_id, display_name, key_fingerprint, status, approved_by, "
            "approved_at, last_verified_at, last_ip, revoked_at, blocked_at, created_at "
            "FROM trusted_devices ORDER BY created_at DESC"
        )).fetchall()
        return [dict(row) for row in rows]


@router.get("/devices/pending")
async def pending_devices(user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    if user.role != "administrator":
        raise HTTPException(status_code=403, detail="Administrator role required.")
    async with get_db() as db:
        rows = await (await db.execute(
            "SELECT device_id,user_id,display_name,key_fingerprint,last_ip,created_at FROM trusted_devices WHERE status='pending' ORDER BY created_at"
        )).fetchall()
        return [dict(row) for row in rows]


@router.post("/devices/{device_id}/approve")
async def approve_device_endpoint(
    device_id: str,
    user_id: Optional[str] = None,
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    if user.role != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")
    from cognishift.app.core.device_security import approve_device as ds_approve_device
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
        target_user_id = row["user_id"]

    success = await ds_approve_device(device_id, target_user_id, user.user_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to approve device.")
    return {"status": "approved", "device_id": device_id, "user_id": target_user_id}


@router.post("/devices/{device_id}/revoke")
async def revoke_device_endpoint(
    device_id: str,
    user_id: Optional[str] = None,
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    if user.role != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")
    from cognishift.app.core.device_security import revoke_device as ds_revoke_device
    await ds_revoke_device(device_id, user_id, user.user_id)
    return {"status": "revoked", "device_id": device_id, "user_id": user_id or "all"}


@router.post("/devices/{device_id}/block")
async def block_device_endpoint(
    device_id: str,
    user_id: Optional[str] = None,
    user: User = Depends(get_current_user),
) -> Dict[str, str]:
    if user.role != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")
    from cognishift.app.core.device_security import block_device as ds_block_device
    await ds_block_device(device_id, user_id, user.user_id)
    return {"status": "blocked", "device_id": device_id, "user_id": user_id or "all"}


# =========================================================================
# SOVEREIGN SECURITY ALERTS & SOC MAILBOX ENDPOINTS
# =========================================================================

@router.get("/alerts/smtp-health")
async def get_smtp_health_endpoint(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Check health and connectivity of the sovereign loopback SMTP listener."""
    if user.role != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")
    from cognishift.core.notifications import check_smtp_health
    return await check_smtp_health()


@router.get("/alerts/mailbox")
async def get_alerts_mailbox(
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve security inbox alerts for Administrator SOC dashboard."""
    if user.role != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")
    import json
    async with get_db() as db:
        rows = await (await db.execute(
            """
            SELECT id, alert_type, severity, subject, sender, recipients,
                   related_user, related_ip, related_device_id, related_run_id,
                   is_read, composition_mode, created_at
            FROM offline_security_alerts
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )).fetchall()

        unread_row = await (await db.execute(
            "SELECT count(*) as unread FROM offline_security_alerts WHERE is_read = 0"
        )).fetchone()
        unread_count = unread_row["unread"] if unread_row else 0

        total_row = await (await db.execute(
            "SELECT count(*) as total FROM offline_security_alerts"
        )).fetchone()
        total_count = total_row["total"] if total_row else 0

        alerts = []
        for r in rows:
            d = dict(r)
            try:
                d["recipients"] = json.loads(d["recipients"])
            except Exception:
                pass
            alerts.append(d)

        return {
            "alerts": alerts,
            "unread_count": unread_count,
            "total_count": total_count,
        }


@router.get("/alerts/{alert_id}")
async def get_alert_detail(
    alert_id: int,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve full detail for a single alert including HTML body and citations."""
    if user.role != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")
    import json
    async with get_db() as db:
        alert_row = await (await db.execute(
            "SELECT * FROM offline_security_alerts WHERE id = ?",
            (alert_id,),
        )).fetchone()
        if not alert_row:
            raise HTTPException(status_code=404, detail="Alert not found.")

        citations = await (await db.execute(
            "SELECT * FROM notification_citations WHERE alert_id = ? ORDER BY citation_index ASC",
            (alert_id,),
        )).fetchall()

        d = dict(alert_row)
        try:
            d["recipients"] = json.loads(d["recipients"])
        except Exception:
            pass
        try:
            d["evidence_pack"] = json.loads(d["evidence_pack_json"])
        except Exception:
            d["evidence_pack"] = {}

        d["citations"] = [dict(c) for c in citations]
        return d


@router.post("/alerts/{alert_id}/read")
async def mark_alert_as_read(
    alert_id: int,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Mark an alert as read in the SOC mailbox."""
    if user.role != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")
    async with get_db() as db:
        await db.execute(
            "UPDATE offline_security_alerts SET is_read = 1 WHERE id = ?",
            (alert_id,),
        )
        await db.commit()
    return {"status": "ok", "id": alert_id, "is_read": 1}


@router.post("/alerts/clear")
async def clear_alerts_mailbox(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Purge all security alerts from mailbox (Admin only)."""
    if user.role != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")
    async with get_db() as db:
        await db.execute("DELETE FROM notification_citations")
        del_a = await db.execute("DELETE FROM offline_security_alerts")
        count = del_a.rowcount
        await db.commit()
    return {"status": "cleared", "deleted_count": count}


@router.post("/alerts/dispatch-test")
async def dispatch_test_alert(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Dispatch a test alert through the local loopback notification pipeline."""
    if user.role != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")
    from cognishift.core.notifications import (
        NotificationEvidencePack,
        NotificationType,
        Severity,
        NotificationCitation,
        CitationClass,
        dispatch_notification_for_event,
    )
    ev = NotificationEvidencePack(
        event_type=NotificationType.TEST_ALERT,
        severity=Severity.LOW,
        actor_id=user.user_id,
        target_user=user.user_id,
        client_ip="127.0.0.1",
        summary="This is a verified test dispatch to validate end-to-end local SMTP delivery on 127.0.0.1:1025.",
        citations=[
            NotificationCitation(
                citation_index=1,
                citation_type=CitationClass.AUDIT,
                display_label="Test Health Verification Token",
                source_id="1",
                validated=True,
            )
        ],
    )
    alert_id, composed, delivered = await dispatch_notification_for_event(ev)
    return {
        "status": "dispatched",
        "alert_id": alert_id,
        "subject": composed.subject,
        "delivered": delivered,
        "composition_mode": composed.composition_mode,
    }

