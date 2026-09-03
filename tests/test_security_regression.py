"""Permanent Security Regression Test Suite for CogniShift.

This suite must pass at EVERY phase gate to guarantee that no subsequent feature
compromises path isolation, Four-Eyes authorization, or air-gap boundaries.
"""
import pytest
import re
from pathlib import Path
from fastapi import HTTPException

from cognishift.core.security import resolve_workspace_path, SecurityError
from cognishift.app.core.auth import User, verify_workspace_access, verify_four_eyes_approval
from cognishift.app.main import app
from fastapi.middleware.cors import CORSMiddleware


def test_regression_path_traversal_impossible():
    """Regression: Directory traversal must ALWAYS fail."""
    traversal_payloads = [
        "../../etc/passwd",
        r"../..\Windows\System32\calc.exe",
        "..%2f..%2fetc%2fpasswd",
        "/etc/shadow",
        r"C:oot.ini",
        r"\server\shareile.txt",
    ]
    for payload in traversal_payloads:
        with pytest.raises((SecurityError, ValueError)):
            resolve_workspace_path(1, payload, purpose="read")


def test_regression_same_person_approval_denied():
    """Regression: Requester cannot self-approve under any circumstances."""
    requester = "EMP-001"
    approver = User(user_id="EMP-001", role="supervisor")
    with pytest.raises(HTTPException) as exc:
        verify_four_eyes_approval(requester_id=requester, approver=approver)
    assert exc.value.status_code == 403


def test_regression_unauthorized_workspace_denied():
    """Regression: Cross-workspace access without explicit permission is forbidden."""
    user = User(user_id="user_a", role="operator", allowed_workspace_ids=[1])
    with pytest.raises(HTTPException) as exc:
        verify_workspace_access(workspace_id=99, user=user)
    assert exc.value.status_code == 403


def test_regression_no_wildcard_cors():
    """Regression: CORS must never be reverted to allow_origins=['*']."""
    cors_middlewares = [m for m in app.user_middleware if m.cls == CORSMiddleware]
    assert len(cors_middlewares) > 0
    allow_origins = cors_middlewares[0].kwargs.get("allow_origins", [])
    assert "*" not in allow_origins


def test_regression_zero_external_cloud_endpoints():
    """Regression: Verify no cloud AI URLs exist in the codebase."""
    src_dir = Path(__file__).resolve().parent.parent / "src" / "cognishift"
    forbidden_domains = ["api.openai.com", "api.anthropic.com", "generativelanguage.googleapis.com"]
    
    for py_file in src_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for domain in forbidden_domains:
            assert domain not in text, f"Forbidden external cloud endpoint '{domain}' found in {py_file}!"
