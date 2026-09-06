"""Structured PendingTask state machine and persistent store for CogniShift.

Enforces bounded continuation:
1. Tracks unfinished agent tasks across multi-turn sessions.
2. Pins authoritative source identity (source_id, workspace_id, filename, checksum, version).
3. Provides atomic Compare-And-Swap (CAS) state transitions for single-winner concurrency.
4. Enforces TTL expiration (default 15m) and persona-switch safety checks.
"""

import json
import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field

from cognishift.app.db.database import get_db

logger = logging.getLogger("cognishift.pending_tasks")


class TaskStatus(str, Enum):
    PROPOSED = "PROPOSED"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    READY = "READY"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PinnedSource(BaseModel):
    """Authoritative pinned identity of an ingested document or workspace source."""
    source_id: int
    workspace_id: int
    filename: str
    version: Optional[str] = None
    checksum: Optional[str] = None
    resolved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PendingTask(BaseModel):
    """Structured, bounded operational task awaiting or undergoing confirmation/execution."""
    id: str
    workspace_id: int
    user_id: str
    originating_run_id: Optional[int] = None
    intent: str
    requested_goal: str
    source_references: Dict[str, Any] = Field(default_factory=dict)
    proposed_steps: List[str] = Field(default_factory=list)
    confirmation_required: bool = True
    status: TaskStatus = TaskStatus.AWAITING_CONFIRMATION
    created_at: str
    updated_at: str
    expires_at: str
    version: int = 1
    execution_started_at: Optional[str] = None
    execution_completed_at: Optional[str] = None
    resulting_run_id: Optional[int] = None

    def is_expired(self) -> bool:
        try:
            exp = datetime.fromisoformat(self.expires_at)
            now = datetime.now(timezone.utc)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return now >= exp
        except Exception:
            return False


AFFIRMATION_PATTERNS = [
    r"^\s*(?:yes|yea|yeah|yep|ok|okay|sure)\s*$",
    r"\b(?:yes|yea|yeah|yep|ok|okay)\s+(?:do\s+it|go\s+ahead|proceed|run\s+it|generate\s+it|execute\s+it)\b",
    r"\b(?:do\s+it|go\s+ahead|okay\s+go\s+ahead|proceed|do\s+that|run\s+it|generate\s+it|execute\s+it|please\s+proceed)\b",
    r"\b(?:yea\s+do\s+it|yes\s+do\s+it|yes\s+please)\b"
]

CANCELLATION_PATTERNS = [
    r"\b(?:don'?t\s+do\s+it|do\s+not\s+do\s+it|cancel\s+that|cancel|never\s*mind|stop|just\s+explain\s+it\s+instead|do\s+not\s+execute|abort)\b",
    r"^\s*no\b"
]


def detect_affirmation_or_cancellation(text: str) -> Tuple[bool, bool]:
    """Detect whether user input is an explicit confirmation, a cancellation, or neither.
    
    Returns:
        (is_affirmation, is_cancellation)
    """
    clean = text.strip().lower()
    for pat in CANCELLATION_PATTERNS:
        if re.search(pat, clean):
            return False, True

    for pat in AFFIRMATION_PATTERNS:
        if re.search(pat, clean):
            return True, False

    return False, False


async def create_pending_task(
    workspace_id: int,
    user_id: str,
    intent: str,
    requested_goal: str,
    source_references: Optional[Dict[str, Any]] = None,
    proposed_steps: Optional[List[str]] = None,
    originating_run_id: Optional[int] = None,
    ttl_seconds: int = 900
) -> PendingTask:
    """Create and persist a new PendingTask with pinned source metadata and expiration TTL."""
    now_utc = datetime.now(timezone.utc)
    expires_utc = now_utc + timedelta(seconds=ttl_seconds)
    task_id = f"task_{uuid.uuid4().hex[:12]}"

    now_iso = now_utc.isoformat()
    exp_iso = expires_utc.isoformat()

    source_refs_dict = source_references or {}
    steps_list = proposed_steps or []

    async with get_db() as db:
        await db.execute(
            """INSERT INTO pending_tasks 
               (id, workspace_id, user_id, originating_run_id, intent, requested_goal,
                source_references, proposed_steps, confirmation_required, status,
                created_at, updated_at, expires_at, version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 'AWAITING_CONFIRMATION', ?, ?, ?, 1)""",
            (
                task_id,
                workspace_id,
                user_id,
                originating_run_id,
                intent,
                requested_goal,
                json.dumps(source_refs_dict),
                json.dumps(steps_list),
                now_iso,
                now_iso,
                exp_iso
            )
        )
        await db.commit()

    return PendingTask(
        id=task_id,
        workspace_id=workspace_id,
        user_id=user_id,
        originating_run_id=originating_run_id,
        intent=intent,
        requested_goal=requested_goal,
        source_references=source_refs_dict,
        proposed_steps=steps_list,
        confirmation_required=True,
        status=TaskStatus.AWAITING_CONFIRMATION,
        created_at=now_iso,
        updated_at=now_iso,
        expires_at=exp_iso,
        version=1
    )


async def get_pending_task(task_id: str) -> Optional[PendingTask]:
    """Retrieve a pending task by ID."""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM pending_tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_pending_task(dict(row))


async def get_active_pending_task(
    workspace_id: int,
    user_id: Optional[str] = None
) -> Optional[PendingTask]:
    """Retrieve the most recent active PendingTask awaiting confirmation within TTL.
    
    CRITICAL PERSONA CHECK:
    If user_id is provided, only returns tasks belonging to that user.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        if user_id:
            cursor = await db.execute(
                """SELECT * FROM pending_tasks 
                   WHERE workspace_id = ? AND user_id = ? 
                     AND status IN ('AWAITING_CONFIRMATION', 'PROPOSED')
                     AND expires_at > ?
                   ORDER BY created_at DESC LIMIT 1""",
                (workspace_id, user_id, now_iso)
            )
        else:
            cursor = await db.execute(
                """SELECT * FROM pending_tasks 
                   WHERE workspace_id = ? 
                     AND status IN ('AWAITING_CONFIRMATION', 'PROPOSED')
                     AND expires_at > ?
                   ORDER BY created_at DESC LIMIT 1""",
                (workspace_id, now_iso)
            )
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_pending_task(dict(row))


async def claim_pending_task_atomic(
    task_id: str,
    expected_version: int,
    claiming_user_id: str
) -> bool:
    """Atomic Compare-And-Swap (CAS) transition from AWAITING_CONFIRMATION -> EXECUTING.
    
    Guarantees single-winner continuation:
    Two simultaneous confirmations will only succeed once.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            """UPDATE pending_tasks
               SET status = 'EXECUTING',
                   version = version + 1,
                   updated_at = ?,
                   execution_started_at = ?
               WHERE id = ? 
                 AND status IN ('AWAITING_CONFIRMATION', 'PROPOSED')
                 AND version = ?
                 AND user_id = ?
                 AND expires_at > ?""",
            (now_iso, now_iso, task_id, expected_version, claiming_user_id, now_iso)
        )
        await db.commit()
        return cursor.rowcount > 0


async def cancel_pending_task(task_id: str, user_id: str) -> bool:
    """Mark a pending task as CANCELLED."""
    now_iso = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            """UPDATE pending_tasks
               SET status = 'CANCELLED',
                   version = version + 1,
                   updated_at = ?
               WHERE id = ? AND user_id = ?
                 AND status IN ('AWAITING_CONFIRMATION', 'PROPOSED', 'READY')""",
            (now_iso, task_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def complete_pending_task(
    task_id: str,
    resulting_run_id: int
) -> bool:
    """Mark a pending task as COMPLETED with the resulting execution run ID."""
    now_iso = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            """UPDATE pending_tasks
               SET status = 'COMPLETED',
                   version = version + 1,
                   resulting_run_id = ?,
                   updated_at = ?,
                   execution_completed_at = ?
               WHERE id = ?""",
            (resulting_run_id, now_iso, now_iso, task_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def fail_pending_task(task_id: str) -> bool:
    """Mark a pending task as FAILED."""
    now_iso = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            """UPDATE pending_tasks
               SET status = 'FAILED',
                   version = version + 1,
                   updated_at = ?
               WHERE id = ?""",
            (now_iso, task_id)
        )
        await db.commit()
        return cursor.rowcount > 0


def _row_to_pending_task(row: dict) -> PendingTask:
    source_refs = {}
    if row.get("source_references"):
        try:
            source_refs = json.loads(row["source_references"])
        except Exception:
            pass

    steps = []
    if row.get("proposed_steps"):
        try:
            steps = json.loads(row["proposed_steps"])
        except Exception:
            pass

    return PendingTask(
        id=row["id"],
        workspace_id=row["workspace_id"],
        user_id=row["user_id"],
        originating_run_id=row.get("originating_run_id"),
        intent=row["intent"],
        requested_goal=row["requested_goal"],
        source_references=source_refs,
        proposed_steps=steps,
        confirmation_required=bool(row.get("confirmation_required", 1)),
        status=TaskStatus(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        expires_at=row["expires_at"],
        version=row.get("version", 1),
        execution_started_at=row.get("execution_started_at"),
        execution_completed_at=row.get("execution_completed_at"),
        resulting_run_id=row.get("resulting_run_id")
    )
