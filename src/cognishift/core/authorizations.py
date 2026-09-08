"""Sovereign Temporary Authorizations Engine & Post-Approval Lifecycle.

Provides authoritative, transactional, and concurrency-safe management of:
- Temporary operational work permits (temporary_authorizations)
- Two independent authenticated supervisor approvals (Four-Eyes principle)
- Atomic Compare-And-Swap (CAS) single-use permit consumption
- Durable post-approval job queue with crash and restart recovery
- Real artifact document registration and notification dispatch
"""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from fastapi import HTTPException, status

from cognishift.app.db.database import get_db
from cognishift.core.artifact_generators import generate_and_register_permit_artifact
from cognishift.core.notifications import (
    CitationClass,
    NotificationCitation,
    NotificationEvidencePack,
    NotificationType,
    Severity,
    dispatch_notification_for_event,
)
from cognishift.core.tools import execute_tool

logger = logging.getLogger(__name__)


def now_iso_utc() -> str:
    """Return timezone-aware ISO-8601 UTC timestamp ending with Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_permit_code() -> str:
    """Generate sovereign human-readable work permit code."""
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    rand_part = uuid.uuid4().hex[:6].upper()
    return f"AUTH-PERMIT-{date_part}-{rand_part}"


async def request_temporary_authorization(
    workspace_id: int,
    user_id: str,
    action: str,
    resource: str,
    valid_duration_minutes: int = 60,
    trusted_device_id: Optional[str] = None,
    requested_by: Optional[str] = None,
    reason: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new temporary authorization request in PENDING_APPROVAL status."""
    t0 = time.perf_counter()
    permit_code = generate_permit_code()
    now = datetime.now(timezone.utc)
    valid_from = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    expires_at = (now + timedelta(minutes=max(5, min(valid_duration_minutes, 1440)))).strftime("%Y-%m-%dT%H:%M:%SZ")
    requester = requested_by or user_id
    corr_id = correlation_id or uuid.uuid4().hex[:12]

    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO temporary_authorizations (
                permit_code, workspace_id, user_id, trusted_device_id,
                action, resource, max_uses, uses, valid_from, expires_at,
                status, requested_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, ?, 'PENDING_APPROVAL', ?, ?)
            RETURNING *
            """,
            (
                permit_code,
                workspace_id,
                user_id,
                trusted_device_id,
                action,
                resource,
                valid_from,
                expires_at,
                requester,
                valid_from,
            ),
        )
        row = await cursor.fetchone()
        permit_id = row["id"]

        # Insert audit log
        audit_details = json.dumps({
            "permit_code": permit_code,
            "target_user": user_id,
            "action": action,
            "resource": resource,
            "valid_minutes": valid_duration_minutes,
            "reason": reason or "Operational requirement",
            "correlation_id": corr_id,
        })
        audit_cursor = await db.execute(
            """
            INSERT INTO audit_events (
                workspace_id, actor_id, action, resource_type, resource_id, details, result
            ) VALUES (?, ?, 'AUTHORIZATION_PERMIT_REQUESTED', 'temporary_authorization', ?, ?, 'success')
            """,
            (workspace_id, requester, permit_id, audit_details),
        )
        audit_id = audit_cursor.lastrowid
        await db.commit()

        # Emit governance notification to supervisors (0/2 pending)
        try:
            ev = NotificationEvidencePack(
                event_type=NotificationType.SENSITIVE_ACTION_REQUESTED,
                severity=Severity.HIGH,
                actor_id=requester,
                target_user=user_id,
                workspace_id=workspace_id,
                tool_name=f"{action} [{resource}]",
                permit_code=permit_code,
                correlation_id=corr_id,
                summary=(
                    f"Temporary operational permit requested by '{requester}' for operator '{user_id}'. "
                    f"Action: {action} on asset {resource}. Valid for {valid_duration_minutes}m. "
                    f"Requires two independent authenticated supervisor approvals prior to execution."
                ),
                citations=[
                    NotificationCitation(
                        citation_index=1,
                        citation_type=CitationClass.AUTHORIZATION,
                        display_label=f"Work Permit Request {permit_code}",
                        source_id=permit_code,
                        validated=True,
                    ),
                    NotificationCitation(
                        citation_index=2,
                        citation_type=CitationClass.AUDIT,
                        display_label=f"Audit Event #{audit_id}",
                        source_id=str(audit_id),
                        validated=True,
                    ),
                ],
            )
            asyncio.create_task(dispatch_notification_for_event(ev))
        except Exception as err:
            logger.warning(f"Could not dispatch notification for permit request: {err}")

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    res = dict(row)
    res["latency_ms"] = elapsed_ms
    res["correlation_id"] = corr_id
    return res


async def approve_authorization_stage(
    permit_id: int,
    approver_id: str,
    approver_role: str,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Process one stage of Four-Eyes supervisor approval.
    
    Standard Flow:
    - Stage 1: First supervisor (e.g. Zara) approves -> PENDING_APPROVAL (1/2)
    - Stage 2: Second distinct supervisor (e.g. Rakshita) approves -> ACTIVE (2/2)
    Critical Path Latency Target: < 1000ms.
    Side effects (artifact generation & email drafting) are queued durably in post_approval_jobs.
    """
    t0 = time.perf_counter()
    corr_id = correlation_id or uuid.uuid4().hex[:12]
    now_str = now_iso_utc()

    if approver_role not in ("supervisor", "administrator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only supervisors and administrators may approve operational permits.",
        )

    async with get_db() as db:
        row = await (await db.execute(
            "SELECT * FROM temporary_authorizations WHERE id = ?",
            (permit_id,),
        )).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Authorization permit not found.")

        permit = dict(row)
        if permit["status"] != "PENDING_APPROVAL":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Permit is not awaiting approval (current status: {permit['status']}).",
            )

        if permit["requested_by"].strip().lower() == approver_id.strip().lower() or permit["user_id"].strip().lower() == approver_id.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Four-Eyes Violation: Permitted operator cannot approve their own authorization permit.",
            )

        # STAGE 1: First supervisor approval
        if not permit.get("first_approver"):
            update_cur = await db.execute(
                """
                UPDATE temporary_authorizations
                SET first_approver = ?, first_approved_at = ?
                WHERE id = ? AND status = 'PENDING_APPROVAL' AND first_approver IS NULL
                RETURNING *
                """,
                (approver_id, now_str, permit_id),
            )
            updated_row = await update_cur.fetchone()
            if not updated_row:
                raise HTTPException(status_code=409, detail="Permit was concurrently updated.")

            audit_cur = await db.execute(
                """
                INSERT INTO audit_events (
                    workspace_id, actor_id, action, resource_type, resource_id, details, result
                ) VALUES (?, ?, 'AUTHORIZATION_STAGE_1_APPROVED', 'temporary_authorization', ?, ?, 'success')
                """,
                (
                    permit["workspace_id"],
                    approver_id,
                    permit_id,
                    json.dumps({
                        "stage": "1/2",
                        "permit_code": permit["permit_code"],
                        "approver": approver_id,
                        "correlation_id": corr_id,
                    }),
                ),
            )
            audit_id = audit_cur.lastrowid
            await db.commit()

            try:
                ev = NotificationEvidencePack(
                    event_type=NotificationType.FIRST_SUPERVISOR_APPROVAL,
                    severity=Severity.MEDIUM,
                    actor_id=approver_id,
                    target_user=permit["user_id"],
                    workspace_id=permit["workspace_id"],
                    tool_name=f"{permit['action']} [{permit['resource']}]",
                    supervisor_1=approver_id,
                    permit_code=permit["permit_code"],
                    correlation_id=corr_id,
                    summary=(
                        f"Four-Eyes Stage 1/2 verified by supervisor '{approver_id}' for permit {permit['permit_code']}. "
                        f"Second independent supervisor approval is required before operational clearance becomes active."
                    ),
                    citations=[
                        NotificationCitation(
                            citation_index=1,
                            citation_type=CitationClass.AUTHORIZATION,
                            display_label=f"Permit {permit['permit_code']} (1/2 Approvals)",
                            source_id=permit["permit_code"],
                            validated=True,
                        ),
                        NotificationCitation(
                            citation_index=2,
                            citation_type=CitationClass.AUDIT,
                            display_label=f"Audit Event #{audit_id}",
                            source_id=str(audit_id),
                            validated=True,
                        ),
                    ],
                )
                asyncio.create_task(dispatch_notification_for_event(ev))
            except Exception as err:
                logger.warning(f"Could not dispatch stage 1 notification: {err}")

            res = dict(updated_row)
            res["approval_stage"] = "1/2"
            res["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            return res

        # STAGE 2: Second distinct supervisor approval -> ACTIVATION
        first_approver = permit["first_approver"].strip().lower()
        if approver_id.strip().lower() == first_approver:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Four-Eyes Violation: Second supervisor approval must be provided by a distinct reviewer (Stage 1 was approved by '{permit['first_approver']}').",
            )

        update_cur = await db.execute(
            """
            UPDATE temporary_authorizations
            SET second_approver = ?, second_approved_at = ?, status = 'ACTIVE'
            WHERE id = ? AND status = 'PENDING_APPROVAL' AND first_approver IS NOT NULL
              AND first_approver != ? AND second_approver IS NULL
            RETURNING *
            """,
            (approver_id, now_str, permit_id, approver_id),
        )
        activated_row = await update_cur.fetchone()
        if not activated_row:
            raise HTTPException(
                status_code=409,
                detail="Permit was already approved concurrently by a second supervisor.",
            )

        audit_cur = await db.execute(
            """
            INSERT INTO audit_events (
                workspace_id, actor_id, action, resource_type, resource_id, details, result
            ) VALUES (?, ?, 'AUTHORIZATION_STAGE_2_ACTIVATED', 'temporary_authorization', ?, ?, 'success')
            """,
            (
                permit["workspace_id"],
                approver_id,
                permit_id,
                json.dumps({
                    "stage": "2/2",
                    "permit_code": permit["permit_code"],
                    "supervisor_1": permit["first_approver"],
                    "supervisor_2": approver_id,
                    "correlation_id": corr_id,
                }),
            ),
        )
        audit_id = audit_cur.lastrowid

        job_cur = await db.execute(
            """
            INSERT INTO post_approval_jobs (
                permit_id, correlation_id, status, attempts, created_at, updated_at
            ) VALUES (?, ?, 'PENDING', 0, ?, ?)
            RETURNING *
            """,
            (permit_id, corr_id, now_str, now_str),
        )
        job_row = await job_cur.fetchone()
        await db.commit()

        # Awaken background worker to process durable post-approval effects (artifact & email)
        asyncio.create_task(process_pending_post_approval_jobs())

        res = dict(activated_row)
        res["approval_stage"] = "2/2"
        res["job_id"] = job_row["id"]
        res["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return res


async def admin_override_authorization(
    permit_id: int,
    admin_id: str,
    admin_role: str,
    justification: str,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Explicit administrator override for authorization permit."""
    t0 = time.perf_counter()
    corr_id = correlation_id or uuid.uuid4().hex[:12]
    now_str = now_iso_utc()

    if admin_role != "administrator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required for authorization override.",
        )
    if not justification or len(justification.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit written justification (minimum 10 characters) is mandatory for administrator override.",
        )

    async with get_db() as db:
        row = await (await db.execute(
            "SELECT * FROM temporary_authorizations WHERE id = ?",
            (permit_id,),
        )).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Authorization permit not found.")

        permit = dict(row)
        if permit["status"] != "PENDING_APPROVAL":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Permit cannot be overridden (status: {permit['status']}).",
            )

        update_cur = await db.execute(
            """
            UPDATE temporary_authorizations
            SET status = 'ACTIVE', admin_override = 1,
                first_approver = COALESCE(first_approver, ?),
                first_approved_at = COALESCE(first_approved_at, ?),
                second_approver = ?, second_approved_at = ?
            WHERE id = ? AND status = 'PENDING_APPROVAL'
            RETURNING *
            """,
            (admin_id, now_str, admin_id, now_str, permit_id),
        )
        activated_row = await update_cur.fetchone()
        if not activated_row:
            raise HTTPException(status_code=409, detail="Permit was concurrently modified.")

        await db.execute(
            """
            INSERT INTO audit_events (
                workspace_id, actor_id, action, resource_type, resource_id, details, result
            ) VALUES (?, ?, 'ADMIN_AUTHORIZATION_OVERRIDE', 'temporary_authorization', ?, ?, 'success')
            """,
            (
                permit["workspace_id"],
                admin_id,
                permit_id,
                json.dumps({
                    "permit_code": permit["permit_code"],
                    "justification": justification,
                    "correlation_id": corr_id,
                }),
            ),
        )

        job_cur = await db.execute(
            """
            INSERT INTO post_approval_jobs (
                permit_id, correlation_id, status, attempts, created_at, updated_at
            ) VALUES (?, ?, 'PENDING', 0, ?, ?)
            RETURNING *
            """,
            (permit_id, corr_id, now_str, now_str),
        )
        job_row = await job_cur.fetchone()
        await db.commit()

        asyncio.create_task(process_pending_post_approval_jobs())

        res = dict(activated_row)
        res["job_id"] = job_row["id"]
        res["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return res


async def execute_authorized_action_atomic(
    permit_code: str,
    caller_user_id: str,
    action: str,
    resource: str,
    caller_device_id: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Atomically consume one-time permit and execute simulated industrial action."""
    t0 = time.perf_counter()
    corr_id = correlation_id or uuid.uuid4().hex[:12]
    now_str = now_iso_utc()
    params = parameters or {}

    async with get_db() as db:
        update_cur = await db.execute(
            """
            UPDATE temporary_authorizations
            SET
                uses = uses + 1,
                status = CASE
                    WHEN uses + 1 >= max_uses THEN 'CONSUMED'
                    ELSE status
                END,
                consumed_at = CASE
                    WHEN uses + 1 >= max_uses THEN ?
                    ELSE consumed_at
                END
            WHERE (permit_code = ? OR CAST(id AS TEXT) = ?)
              AND status = 'ACTIVE'
              AND user_id = ?
              AND action = ?
              AND resource = ?
              AND uses < max_uses
              AND valid_from <= ?
              AND expires_at > ?
              AND (
                  trusted_device_id IS NULL
                  OR trusted_device_id = ?
              )
            RETURNING *
            """,
            (
                now_str,
                permit_code,
                str(permit_code),
                caller_user_id,
                action,
                resource,
                now_str,
                now_str,
                caller_device_id,
            ),
        )
        consumed_row = await update_cur.fetchone()

        if consumed_row:
            permit = dict(consumed_row)
            permit_id = permit["id"]
            workspace_id = permit["workspace_id"]

            sim_result = await execute_tool(
                tool_name=action,
                parameters={**params, "equipment_id": resource, "resource": resource},
                workspace_id=workspace_id,
            )

            audit_cur = await db.execute(
                """
                INSERT INTO audit_events (
                    workspace_id, actor_id, action, resource_type, resource_id, details, result
                ) VALUES (?, ?, 'AUTHORIZATION_PERMIT_CONSUMED', 'temporary_authorization', ?, ?, 'success')
                """,
                (
                    workspace_id,
                    caller_user_id,
                    permit_id,
                    json.dumps({
                        "permit_code": permit["permit_code"],
                        "resource": resource,
                        "action": action,
                        "tool_result": sim_result,
                        "remaining_uses": max(0, permit["max_uses"] - permit["uses"]),
                        "correlation_id": corr_id,
                    }),
                ),
            )
            audit_id = audit_cur.lastrowid
            await db.commit()

            try:
                ev = NotificationEvidencePack(
                    event_type=NotificationType.AUTHORIZATION_CONSUMED,
                    severity=Severity.HIGH,
                    actor_id=caller_user_id,
                    target_user=caller_user_id,
                    workspace_id=workspace_id,
                    tool_name=f"{action} [{resource}]",
                    permit_code=permit["permit_code"],
                    uses_remaining=0,
                    correlation_id=corr_id,
                    summary=(
                        f"Operational permit '{permit['permit_code']}' successfully executed by operator '{caller_user_id}'. "
                        f"Target asset: {resource}. Remaining permitted uses: 0. "
                        f"Permit is now permanently CONSUMED. Execution result: {sim_result}"
                    ),
                    citations=[
                        NotificationCitation(
                            citation_index=1,
                            citation_type=CitationClass.AUTHORIZATION,
                            display_label=f"Permit {permit['permit_code']} (CONSUMED)",
                            source_id=permit["permit_code"],
                            validated=True,
                        ),
                        NotificationCitation(
                            citation_index=2,
                            citation_type=CitationClass.AUDIT,
                            display_label=f"Consumption Audit Event #{audit_id}",
                            source_id=str(audit_id),
                            validated=True,
                        ),
                    ],
                )
                asyncio.create_task(dispatch_notification_for_event(ev))
            except Exception as err:
                logger.warning(f"Could not dispatch consumed notification: {err}")

            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "status": "CONSUMED",
                "permit_code": permit["permit_code"],
                "user_id": caller_user_id,
                "resource": resource,
                "action": action,
                "uses": permit["uses"],
                "max_uses": permit["max_uses"],
                "remaining_uses": 0,
                "consumed_at": permit["consumed_at"],
                "simulated_result": sim_result,
                "latency_ms": elapsed_ms,
                "disclaimer": "[SIMULATED INDUSTRIAL ACTION - SIH FINALS PROTOTYPE]",
            }

        inspect_row = await (await db.execute(
            "SELECT * FROM temporary_authorizations WHERE permit_code = ? OR CAST(id AS TEXT) = ?",
            (permit_code, str(permit_code)),
        )).fetchone()

        if not inspect_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AUTHORIZATION_NOT_FOUND: Authorization permit '{permit_code}' does not exist.",
            )

        p = dict(inspect_row)
        # Validation checks in priority order:
        if p["user_id"].strip().lower() != caller_user_id.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"AUTHORIZATION_NOT_OWNED: Permit belongs to user '{p['user_id']}', not caller '{caller_user_id}'.",
            )
        if p["action"].strip().lower() != action.strip().lower() or p["resource"].strip().lower() != resource.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"AUTHORIZATION_SCOPE_MISMATCH: Permit authorizes '{p['action']}' on '{p['resource']}', requested '{action}' on '{resource}'.",
            )
        if p.get("trusted_device_id") and (not caller_device_id or p["trusted_device_id"] != caller_device_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AUTHORIZATION_DEVICE_MISMATCH: Calling hardware key does not match the device bound to this permit.",
            )
        if p["status"] == "REVOKED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AUTHORIZATION_REVOKED: This permit has been revoked by a supervisor.",
            )
        if p["status"] == "CONSUMED" or p["uses"] >= p["max_uses"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AUTHORIZATION_CONSUMED: This one-time operational permit has already been consumed.",
            )
        if p["status"] != "ACTIVE":
            if p["status"] == "PENDING_APPROVAL":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="AUTHORIZATION_NOT_ACTIVE: Dual supervisor Four-Eyes approvals are still pending.",
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"AUTHORIZATION_NOT_ACTIVE: Permit is not in ACTIVE status (current status: {p['status']}).",
            )
        if p.get("valid_from") and p["valid_from"] > now_str:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"AUTHORIZATION_NOT_YET_VALID: Permit validity begins at {p['valid_from']}.",
            )
        if p["expires_at"] <= now_str or p["status"] == "EXPIRED":
            await db.execute(
                "UPDATE temporary_authorizations SET status = 'EXPIRED' WHERE id = ?",
                (p["id"],),
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"AUTHORIZATION_EXPIRED: Permit expired at {p['expires_at']}.",
            )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"AUTHORIZATION_DENIED: Cannot execute permit with current status '{p['status']}'.",
        )


async def revoke_authorization(
    permit_id: int,
    caller_id: str,
    caller_role: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Revoke an active or pending authorization permit."""
    if caller_role not in ("supervisor", "administrator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only supervisors and administrators can revoke authorization permits.",
        )

    async with get_db() as db:
        cur = await db.execute(
            """
            UPDATE temporary_authorizations
            SET status = 'REVOKED'
            WHERE id = ? AND status IN ('PENDING_APPROVAL', 'ACTIVE')
            RETURNING *
            """,
            (permit_id,),
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Permit not found or is already in a terminal state.",
            )

        permit = dict(row)
        await db.execute(
            """
            INSERT INTO audit_events (
                workspace_id, actor_id, action, resource_type, resource_id, details, result
            ) VALUES (?, ?, 'AUTHORIZATION_PERMIT_REVOKED', 'temporary_authorization', ?, ?, 'success')
            """,
            (
                permit["workspace_id"],
                caller_id,
                permit_id,
                json.dumps({"reason": reason or "Revoked by supervisor", "permit_code": permit["permit_code"]}),
            ),
        )
        await db.commit()
        return permit


_worker_lock: Optional[asyncio.Lock] = None
_worker_lock_loop = None


def _get_worker_lock() -> asyncio.Lock:
    global _worker_lock, _worker_lock_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _worker_lock is None or _worker_lock_loop != current_loop:
        _worker_lock = asyncio.Lock()
        _worker_lock_loop = current_loop
    return _worker_lock


async def process_pending_post_approval_jobs() -> int:
    """Process any pending post-approval jobs in the durable SQLite queue."""
    processed_count = 0
    lock = _get_worker_lock()
    async with lock:
        async with get_db() as db:
            jobs = await (await db.execute(
                "SELECT * FROM post_approval_jobs WHERE status = 'PENDING' ORDER BY id ASC",
            )).fetchall()

        for job in jobs:
            job_id = job["id"]
            permit_id = job["permit_id"]
            corr_id = job["correlation_id"]

            async with get_db() as db:
                await db.execute(
                    "UPDATE post_approval_jobs SET status = 'PROCESSING', attempts = attempts + 1, updated_at = ? WHERE id = ?",
                    (now_iso_utc(), job_id),
                )
                await db.commit()

                permit_row = await (await db.execute(
                    "SELECT * FROM temporary_authorizations WHERE id = ?",
                    (permit_id,),
                )).fetchone()

            if not permit_row:
                async with get_db() as db:
                    await db.execute(
                        "UPDATE post_approval_jobs SET status = 'FAILED', error_message = 'Permit not found', updated_at = ? WHERE id = ?",
                        (now_iso_utc(), job_id),
                    )
                    await db.commit()
                continue

            permit = dict(permit_row)
            workspace_id = permit["workspace_id"]
            permit_code = permit["permit_code"]

            try:
                t_art0 = time.perf_counter()
                artifact_record = await generate_and_register_permit_artifact(
                    workspace_id=workspace_id,
                    permit_data=permit,
                )
                artifact_id = artifact_record["id"]
                artifact_filename = artifact_record["filename"]
                artifact_path = artifact_record.get("relative_path", "")
                art_ms = (time.perf_counter() - t_art0) * 1000

                async with get_db() as db:
                    await db.execute(
                        "UPDATE temporary_authorizations SET artifact_id = ? WHERE id = ?",
                        (artifact_id, permit_id),
                    )
                    await db.commit()

                ev = NotificationEvidencePack(
                    event_type=NotificationType.ACCESS_AUTHORIZATION,
                    severity=Severity.HIGH,
                    actor_id=permit.get("second_approver") or "supervisor",
                    target_user=permit["user_id"],
                    workspace_id=workspace_id,
                    tool_name=f"{permit['action']} [{permit['resource']}]",
                    supervisor_1=permit.get("first_approver"),
                    supervisor_2=permit.get("second_approver"),
                    permit_code=permit_code,
                    uses_remaining=permit["max_uses"],
                    correlation_id=corr_id,
                    artifact_id=artifact_id,
                    artifact_name=artifact_filename,
                    artifact_path=artifact_path,
                    summary=(
                        f"Temporary operational work permit '{permit_code}' granted to operator '{permit['user_id']}'. "
                        f"Target asset: {permit['resource']}. Authorized action: {permit['action']}. "
                        f"Permitted uses: 1. Verified by two independent authenticated supervisor approvals "
                        f"({permit.get('first_approver')} and {permit.get('second_approver')}). "
                        f"Valid until: {permit['expires_at']}. [SIMULATED INDUSTRIAL ACTION - SIH FINALS PROTOTYPE]"
                    ),
                    citations=[
                        NotificationCitation(
                            citation_index=1,
                            citation_type=CitationClass.AUTHORIZATION,
                            display_label=f"Work Permit {permit_code} (ACTIVE)",
                            source_id=permit_code,
                            validated=True,
                        ),
                        NotificationCitation(
                            citation_index=2,
                            citation_type=CitationClass.ARTIFACT,
                            display_label=f"Permit Document ({artifact_filename})",
                            source_id=str(artifact_id),
                            validated=True,
                        ),
                    ],
                )

                alert_id, composed, delivered = await dispatch_notification_for_event(ev)

                if alert_id and artifact_id:
                    try:
                        from cognishift.core.security import resolve_workspace_path
                        art_file_path = resolve_workspace_path(workspace_id, artifact_path, purpose="read")
                        f_size = art_file_path.stat().st_size if art_file_path.exists() else 0
                        async with get_db() as db:
                            await db.execute(
                                """
                                INSERT INTO mail_attachments (
                                    alert_id, uploader_user_id, filename, content_type, file_size, storage_path,
                                    sha256_hash, artifact_id, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    alert_id,
                                    permit.get("second_approver") or "system",
                                    artifact_filename,
                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    f_size,
                                    str(art_file_path),
                                    artifact_record.get("sha256_hash", ""),
                                    artifact_id,
                                    now_iso_utc(),
                                ),
                            )
                            await db.commit()
                    except Exception as att_err:
                        logger.warning(f"Could not link artifact attachment for alert {alert_id}: {att_err}")

                async with get_db() as db:
                    await db.execute(
                        """
                        UPDATE post_approval_jobs
                        SET status = 'COMPLETED', artifact_id = ?, artifact_path = ?,
                            alert_id = ?, completed_at = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (artifact_id, artifact_path, alert_id, now_iso_utc(), now_iso_utc(), job_id),
                    )
                    await db.commit()

                processed_count += 1
                logger.info(
                    f"Post-approval job #{job_id} for permit {permit_code} completed successfully. "
                    f"Artifact #{artifact_id} generated in {art_ms:.1f}ms, Alert #{alert_id} dispatched."
                )

            except Exception as exc:
                logger.error(f"Error processing post-approval job #{job_id}: {exc}", exc_info=True)
                async with get_db() as db:
                    await db.execute(
                        "UPDATE post_approval_jobs SET status = 'FAILED', error_message = ?, updated_at = ? WHERE id = ?",
                        (str(exc), now_iso_utc(), job_id),
                    )
                    await db.commit()

    return processed_count
