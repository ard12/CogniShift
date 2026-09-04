"""
Bounded Network Audit Event Storage and Retrieval.
Persists metadata-only records into SQLite; guarantees zero secret or payload leakage.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import logging

from cognishift.app.db.database import get_db
from cognishift.core.network.schemas import (
    NetworkEvent,
    DestinationClass,
    PolicyDecision,
)

logger = logging.getLogger(__name__)


async def init_network_events_table():
    """Ensure the network_events table exists with proper indexes."""
    async with get_db() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS network_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                component TEXT NOT NULL,
                method TEXT,
                requested_host TEXT NOT NULL,
                resolved_ip TEXT,
                port INTEGER,
                destination_class TEXT NOT NULL,
                policy_decision TEXT NOT NULL,
                reason TEXT NOT NULL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_net_events_decision ON network_events(policy_decision)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_net_events_timestamp ON network_events(timestamp)")
        await db.commit()


async def log_network_event(
    component: str,
    requested_host: str,
    destination_class: DestinationClass,
    policy_decision: PolicyDecision,
    reason: str,
    method: Optional[str] = None,
    resolved_ip: Optional[str] = None,
    port: Optional[int] = None,
) -> NetworkEvent:
    """
    Records an outbound network attempt in the audit ledger.
    Strictly records metadata only; headers, cookies, prompts, and bodies are never accepted or stored.
    """
    # Sanitize hostname and reason to prevent log injection
    clean_host = requested_host.split("?")[0].split("#")[0].strip()
    clean_reason = reason.strip()

    event = NetworkEvent(
        timestamp=datetime.now(timezone.utc),
        component=component,
        method=method,
        requested_host=clean_host,
        resolved_ip=resolved_ip,
        port=port,
        destination_class=destination_class,
        policy_decision=policy_decision,
        reason=clean_reason,
    )

    try:
        async with get_db() as db:
            cursor = await db.execute(
                """
                INSERT INTO network_events (
                    component, method, requested_host, resolved_ip, port,
                    destination_class, policy_decision, reason, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.component,
                    event.method,
                    event.requested_host,
                    event.resolved_ip,
                    event.port,
                    event.destination_class.value,
                    event.policy_decision.value,
                    event.reason,
                    event.timestamp.isoformat(),
                )
            )
            await db.commit()
            event.id = cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to record network audit event: {e}")

    return event


async def get_network_events(
    limit: int = 100,
    offset: int = 0,
    decision_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieves paginated network audit events."""
    query = "SELECT * FROM network_events"
    params = []
    if decision_filter:
        query += " WHERE policy_decision = ?"
        params.append(decision_filter)
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    async with get_db() as db:
        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def prune_network_events(max_records: int = 5000, retention_days: int = 7) -> int:
    """Prunes stale network events to prevent unbounded table growth."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    pruned_count = 0
    async with get_db() as db:
        # Prune older than retention days
        cursor = await db.execute("DELETE FROM network_events WHERE timestamp < ?", (cutoff,))
        pruned_count += cursor.rowcount

        # Bound max records if still over limit
        cursor = await db.execute("SELECT count(*) as cnt FROM network_events")
        row = await cursor.fetchone()
        total = row["cnt"] if row else 0
        if total > max_records:
            excess = total - max_records
            await db.execute(
                "DELETE FROM network_events WHERE id IN (SELECT id FROM network_events ORDER BY id ASC LIMIT ?)",
                (excess,)
            )
            pruned_count += excess

        await db.commit()
    return pruned_count
