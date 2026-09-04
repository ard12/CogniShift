"""
Sovereignty & Network Audit API Endpoints.
Provides authenticated access to sovereignty status and the network audit event ledger.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status

from cognishift.app.config import settings
from cognishift.app.core.auth import get_current_user, User
from cognishift.core.network.preflight import run_network_preflight
from cognishift.core.network.events import get_network_events
from cognishift.core.network.guard import get_active_network_policy
from cognishift.app.db.database import get_db

router = APIRouter(prefix="/api/v1/system", tags=["System"])


@router.get("/sovereignty")
async def get_sovereignty_status(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns verified system sovereignty status and local component readiness.
    Authenticated endpoint; does not expose confidential secrets or raw request data.
    """
    policy = get_active_network_policy()
    preflight = await run_network_preflight()

    # Query count of blocked events
    blocked_count = 0
    try:
        async with get_db() as db:
            cursor = await db.execute("SELECT count(*) as cnt FROM network_events WHERE policy_decision = 'BLOCKED'")
            row = await cursor.fetchone()
            blocked_count = row["cnt"] if row else 0
    except Exception:
        pass

    component_summary = {
        name: {
            "status": comp.status,
            "details": comp.details,
            "is_ready": comp.is_ready
        }
        for name, comp in preflight.components.items()
    }

    return {
        "policy_mode": policy.mode.value,
        "sovereignty_enforced": policy.mode.value == "strict",
        "public_egress_allowed": policy.mode.value != "strict",
        "all_components_ready": preflight.all_ready,
        "components": component_summary,
        "allowed_destinations_count": len(policy.allowed_destinations),
        "total_blocked_attempts": blocked_count,
        "user_role": current_user.role,
    }


@router.get("/network-events")
async def list_network_events(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    decision: Optional[str] = Query(default=None, pattern="^(ALLOWED|BLOCKED)$"),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Retrieves paginated network audit events.
    Strictly authenticated; metadata only. Zero confidential tokens or payload bodies.
    """
    events = await get_network_events(limit=limit, offset=offset, decision_filter=decision)
    return {
        "total": len(events),
        "limit": limit,
        "offset": offset,
        "events": events
    }
