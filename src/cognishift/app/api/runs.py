import json
import logging
from fastapi import APIRouter, HTTPException, Query, Depends, Request, status
from typing import List, Optional, Any, Dict

from cognishift.app.db.database import get_db
from cognishift.app.db.models import RunCreate, RunResponse, RunEventResponse
from cognishift.app.core.auth import get_current_user, verify_workspace_access, User
from cognishift.core.engine import execute_agent_run, resume_agent_run
from cognishift.core.network.guard import get_active_network_policy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/runs", tags=["Runs"])


def _safe_json_loads(val: Optional[str]) -> Dict[str, Any]:
    if not val:
        return {}
    try:
        data = json.loads(val)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _format_run_response(row: Any) -> RunResponse:
    d = dict(row)
    if d.get("routing_info") and isinstance(d["routing_info"], str):
        try:
            d["routing_info"] = json.loads(d["routing_info"])
        except Exception:
            d["routing_info"] = None
    return RunResponse.model_validate(d)


@router.post("", response_model=RunResponse)
async def create_run(
    run_req: RunCreate,
    request: Request,
    user: User = Depends(get_current_user)
):
    """Trigger a new agent reasoning run.
    
    P0-6 ENFORCEMENT:
    Requester identity strictly derives from the authenticated server-side user context.
    Any 'user_id' supplied inside the request body is discarded.
    """
    verify_workspace_access(run_req.workspace_id, user)
    try:
        run_res = await execute_agent_run(
            workspace_id=run_req.workspace_id,
            agent_id=run_req.agent_id,
            input_text=run_req.input_text or "",
            user_id=user.user_id,
            input_image_path=run_req.input_image_path,
            conversation_history=run_req.conversation_history
        )
        async with get_db() as db:
            await db.execute(
                "INSERT INTO audit_events (workspace_id,actor_id,action,resource_type,resource_id,details,result) VALUES (?,?, 'agent_run_recorded','agent_run',?,?,?)",
                (run_req.workspace_id, user.user_id, run_res.id, f"status={run_res.status}; authenticated request recorded", "success" if run_res.status != "failed" else "failed"),
            )
            await db.commit()
        return run_res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Engine execution error for run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while executing the agent run. Please review system audit logs.")


@router.get("", response_model=List[RunResponse])
async def list_runs(
    workspace_id: Optional[int] = Query(None, description="Filter runs by workspace"),
    agent_id: Optional[int] = Query(None, description="Filter runs by agent"),
    user: User = Depends(get_current_user)
):
    """List past agent runs authorized for current user."""
    async with get_db() as db:
        clauses = []
        params = []
        if workspace_id is not None:
            verify_workspace_access(workspace_id, user)
            clauses.append("workspace_id = ?")
            params.append(workspace_id)
        else:
            if user.role != "administrator":
                placeholders = ",".join("?" for _ in user.allowed_workspace_ids)
                if not placeholders:
                    return []
                clauses.append(f"workspace_id IN ({placeholders})")
                params.extend(user.allowed_workspace_ids)

        if agent_id is not None:
            clauses.append("agent_id = ?")
            params.append(agent_id)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM agent_runs {where_sql} ORDER BY started_at DESC, id DESC"
        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        return [_format_run_response(r) for r in rows]


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: int,
    user: User = Depends(get_current_user)
):
    """Get status and result for a specific run with workspace access check."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")
        verify_workspace_access(row["workspace_id"], user)
        return _format_run_response(row)


@router.get("/{run_id}/events", response_model=List[RunEventResponse])
async def get_run_events(
    run_id: int,
    user: User = Depends(get_current_user)
):
    """Get the event timeline for a run with workspace access check."""
    async with get_db() as db:
        cursor = await db.execute("SELECT workspace_id FROM agent_runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")
        verify_workspace_access(row["workspace_id"], user)

        cursor = await db.execute(
            "SELECT * FROM run_events WHERE run_id = ? ORDER BY created_at ASC, id ASC",
            (run_id,)
        )
        rows = await cursor.fetchall()
        return [RunEventResponse.model_validate(dict(r)) for r in rows]


@router.get("/{run_id}/status-summary")
async def get_run_status_summary(run_id: int, request: Request, user: User = Depends(get_current_user)):
    """Return a compact, evidence-backed visualization of stages that actually occurred."""
    async with get_db() as db:
        run = await (await db.execute("SELECT * FROM agent_runs WHERE id=?", (run_id,))).fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        verify_workspace_access(run["workspace_id"], user)
        events = await (await db.execute("SELECT * FROM run_events WHERE run_id=? ORDER BY id", (run_id,))).fetchall()
        approval = await (await db.execute("SELECT * FROM approval_requests WHERE run_id=? ORDER BY id DESC LIMIT 1", (run_id,))).fetchone()
        audit = await (await db.execute("SELECT id FROM audit_events WHERE resource_type='agent_run' AND resource_id=? ORDER BY id DESC LIMIT 1", (run_id,))).fetchone()

    by_type = {}
    for event in events:
        by_type.setdefault(event["event_type"], []).append(event)
    stages = []
    classified = by_type.get("task_classified", [])
    if classified:
        data = _safe_json_loads(classified[-1]["structured_data"])
        stages.append({"key": "task", "label": "Task Detected", "value": str(data.get("task_type", "unknown")).replace("_", " ").title(), "status": "complete"})
    selected = by_type.get("model_selected", [])
    if selected:
        data = _safe_json_loads(selected[-1]["structured_data"])
        vision = by_type.get("vision_completed", [])
        specialist = None
        if vision:
            specialist = _safe_json_loads(vision[-1]["structured_data"]).get("model")
        model_value = specialist or data.get("selected_model") or run["model_name"] or "Unavailable"
        detail = data.get("reason")
        if specialist and run["model_name"] and run["model_name"] != specialist:
            model_value = f"{specialist} + {run['model_name']}"
            detail = f"{specialist} inspected the image; {run['model_name']} orchestrated the response"
        stages.append({"key": "model", "label": "Model Selected", "value": model_value, "detail": detail, "status": "complete" if model_value != "Unavailable" else "unavailable"})
    if run["sources_used"]:
        stages.append({"key": "source", "label": "Data Source Used", "value": run["sources_used"], "status": "complete"})
    if run["operating_mode"]:
        stages.append({"key": "location", "label": "Execution Location", "value": "LOCAL" if run["operating_mode"].lower() == "local" else run["operating_mode"].upper(), "status": "complete"})
    policy = get_active_network_policy()
    stages.append({"key": "network", "label": "Network Status", "value": "External Internet Blocked" if policy.mode.value == "strict" else "Not Verified", "detail": f"Policy: {policy.mode.value}", "status": "complete" if policy.mode.value == "strict" else "warning"})
    tool_events = by_type.get("tool_executing", []) + by_type.get("tool_executed", [])
    sandbox_events = [e for e in events if "sandbox" in e["event_type"]]
    if tool_events or sandbox_events:
        label = "Isolated Sandbox Used" if sandbox_events else "Tool Used"
        stages.append({"key": "tool", "label": "Tool / Sandbox", "value": label, "detail": (tool_events[-1]["message"] if tool_events else sandbox_events[-1]["message"]), "status": "complete"})
    stages.append({"key": "security", "label": "Security Checks", "value": "User Verified · Device Trusted · Workspace Authorized" if getattr(request.state, "device_trusted", False) else "User Verified · Device Not Verified · Workspace Authorized", "status": "complete" if getattr(request.state, "device_trusted", False) else "warning"})
    if approval:
        stages.append({"key": "approval", "label": "Approval Status", "value": str(approval["status"]).title(), "detail": f"{approval['risk_level'] or 'sensitive'} action; {approval['required_approvals']} approval(s) required", "status": "complete" if approval["status"] == "approved" else "warning"})
    stages.append({"key": "audit", "label": "Audit Status", "value": "Recorded" if audit else "Not Verified", "status": "complete" if audit else "warning"})
    return {"run_id": run_id, "run_status": run["status"], "stages": stages}


@router.post("/{run_id}/resume", response_model=RunResponse)
async def resume_run(
    run_id: int,
    user: User = Depends(get_current_user)
):
    """Resume a paused run with supervisor verification."""
    if user.role not in ["supervisor", "administrator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: Role '{user.role}' cannot resume runs."
        )

    async with get_db() as db:
        cursor = await db.execute("SELECT workspace_id FROM agent_runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")
        verify_workspace_access(row["workspace_id"], user)

    try:
        run_res = await resume_agent_run(run_id=run_id)
        return run_res
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to resume run {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while resuming the agent run. Please review system audit logs.")
