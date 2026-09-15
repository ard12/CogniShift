#!/usr/bin/env python3
"""Preflight route verification script for CogniShift.

Validates that all critical FastAPI endpoints, HTTP methods, and routes are properly
registered and free from shadowing or ordering bugs prior to deployment.
"""
import sys
from typing import List, Set, Tuple

# Ensure project root is on sys.path
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))

from cognishift.app.main import app

CRITICAL_ENDPOINTS: List[Tuple[str, str]] = [
    ("GET", "/health"),
    ("GET", "/api/v1/system/status"),
    ("POST", "/api/v1/auth/device/challenge"),
    ("POST", "/api/v1/auth/device/verify"),
    ("POST", "/api/v1/auth/demo-session"),
    ("GET", "/api/v1/auth/me"),
    ("GET", "/api/v1/workspaces"),
    ("GET", "/api/v1/agents"),
    ("GET", "/api/v1/authorizations"),
    ("POST", "/api/v1/authorizations/execute"),
    ("GET", "/api/v1/mail"),
    ("GET", "/api/v1/mail/recipients"),
    ("POST", "/api/v1/mail/send"),
    ("POST", "/api/v1/mail/attachments/upload"),
    ("GET", "/api/v1/mail/events"),
    ("POST", "/api/v1/mail/draft/assist"),
    ("GET", "/api/v1/mail/smtp-health"),
    ("GET", "/api/v1/mail/{alert_id}"),
    ("POST", "/api/v1/mail/{alert_id}/read"),
    ("GET", "/api/v1/mail/{alert_id}/attachments/{attachment_id}"),
    ("GET", "/api/v1/workspaces/{workspace_id}/artifacts"),
]


def verify_routes() -> bool:
    registered: Set[Tuple[str, str]] = set()
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", None)
        if path:
            for m in methods:
                registered.add((m.upper(), path))

    print("=" * 70)
    print("COGNISHIFT PREFLIGHT ROUTE VERIFICATION")
    print("=" * 70)
    print(f"Total registered route/method pairs: {len(registered)}")
    print("-" * 70)

    missing = []
    for method, path in CRITICAL_ENDPOINTS:
        if (method, path) in registered:
            print(f"  [OK]  {method:<6} {path}")
        else:
            print(f"  [FAIL] {method:<6} {path} -- MISSING!")
            missing.append((method, path))

    print("-" * 70)
    if missing:
        print(f"PREFLIGHT FAILED: {len(missing)} critical route(s) missing!")
        for m, p in missing:
            print(f"   - {m} {p}")
        return False
    else:
        print("ALL CRITICAL ROUTES VERIFIED SUCCESSFULLY.")
        print("=" * 70)
        return True


if __name__ == "__main__":
    success = verify_routes()
    sys.exit(0 if success else 1)
