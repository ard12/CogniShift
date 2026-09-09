"""Time utilities for CogniShift.

Canonical representation: timezone-aware ISO-8601 UTC with 'Z' suffix.
No naive datetimes. No manual +05:30 arithmetic on the backend.
Frontend formats UTC to Asia/Kolkata via Intl.DateTimeFormat.
"""
from datetime import datetime, timezone
from typing import Optional


def now_iso_utc() -> str:
    """Return current timestamp as ISO-8601 UTC string (e.g. '2026-09-08T18:42:31.123Z')."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def now_iso_utc_sec() -> str:
    """Return current timestamp with second precision (e.g. '2026-09-08T18:42:31Z')."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_iso_utc(ts_str: Optional[str]) -> str:
    """Normalize SQLite timestamp string into ISO-8601 UTC with Z suffix."""
    if not ts_str:
        return ""
    ts = str(ts_str).strip()
    if not ts.endswith("Z") and not ("+" in ts[10:] or "-" in ts[10:]):
        return ts.replace(" ", "T") + "Z"
    return ts
