"""Phase 0 Security & Four-Eyes Baseline Verification Tests."""
import pytest
from pathlib import Path
from fastapi import HTTPException

from cognishift.core.security import resolve_workspace_path, SecurityError, get_workspace_root
from cognishift.app.core.auth import User, verify_workspace_access, verify_four_eyes_approval
from cognishift.app.main import app
from fastapi.middleware.cors import CORSMiddleware


def test_path_traversal_rejected():
    """Verify that path traversal and absolute paths are strictly blocked."""
    # 1. Directory traversal tokens
    with pytest.raises(SecurityError, match="traversal"):
        resolve_workspace_path(1, "../../etc/passwd", purpose="read")

    with pytest.raises(SecurityError, match="traversal"):
        resolve_workspace_path(1, "sub/../../secret.txt", purpose="read")

    # 2. Absolute paths
    with pytest.raises(SecurityError, match="Absolute paths are forbidden"):
        resolve_workspace_path(1, "C:/Windows/System32/cmd.exe", purpose="read")

    with pytest.raises(SecurityError, match="Absolute paths are forbidden"):
        resolve_workspace_path(1, "/etc/shadow", purpose="read")

    # 3. Empty or null paths
    with pytest.raises(SecurityError, match="empty"):
        resolve_workspace_path(1, "", purpose="read")

    with pytest.raises(SecurityError, match="Null bytes"):
        resolve_workspace_path(1, "safe" + chr(0) + "file.txt", purpose="read")


def test_valid_workspace_path_resolution(tmp_path, monkeypatch):
    """Verify that canonical paths resolve strictly within workspace root."""
    monkeypatch.setattr("cognishift.app.config.settings.data_dir", tmp_path)
    
    # Resolving a safe relative path for writing
    resolved = resolve_workspace_path(1, "documents/test.txt", purpose="write", allow_create_parent=True)
    ws_root = get_workspace_root(1)
    
    assert resolved.is_relative_to(ws_root)
    assert resolved == ws_root / "documents" / "test.txt"
    assert resolved.parent.exists()


def test_four_eyes_identity_enforced():
    """Verify that Four-Eyes authorization rules are mathematically enforced."""
    operator_user = User(user_id="operator_alice", role="operator")
    supervisor_bob = User(user_id="supervisor_bob", role="supervisor")
    admin_charlie = User(user_id="admin_charlie", role="administrator")

    # Rule 1: Requester cannot self-approve, even if they have supervisor role
    self_supervisor = User(user_id="operator_alice", role="supervisor")
    with pytest.raises(HTTPException) as exc1:
        verify_four_eyes_approval(requester_id="operator_alice", approver=self_supervisor)
    assert exc1.value.status_code == 403
    assert "cannot approve their own request" in exc1.value.detail

    # Rule 2: Operator role cannot approve high-risk action
    operator_dan = User(user_id="operator_dan", role="operator")
    with pytest.raises(HTTPException) as exc2:
        verify_four_eyes_approval(requester_id="operator_alice", approver=operator_dan)
    assert exc2.value.status_code == 403
    assert "Only 'supervisor' or 'administrator' can authorize" in exc2.value.detail

    # Rule 3: Distinct supervisor CAN approve
    verify_four_eyes_approval(requester_id="operator_alice", approver=supervisor_bob)

    # Rule 4: Distinct administrator CAN approve
    verify_four_eyes_approval(requester_id="operator_alice", approver=admin_charlie)


def test_workspace_access_control():
    """Verify that users cannot access unauthorized workspaces (IDOR prevention)."""
    user_ws1 = User(user_id="alice", role="operator", allowed_workspace_ids=[1])
    admin_user = User(user_id="admin", role="administrator", allowed_workspace_ids=[1])

    # Authorized workspace
    verify_workspace_access(1, user_ws1)

    # Unauthorized workspace (IDOR attempt)
    with pytest.raises(HTTPException) as exc:
        verify_workspace_access(2, user_ws1)
    assert exc.value.status_code == 403
    assert "not authorized for Workspace #2" in exc.value.detail

    # Administrator can access any workspace
    verify_workspace_access(2, admin_user)


def test_cors_origins_restricted():
    """Verify that wildcard CORS is disabled."""
    cors_middlewares = [m for m in app.user_middleware if m.cls == CORSMiddleware]
    assert len(cors_middlewares) > 0
    cors_options = cors_middlewares[0].kwargs
    
    allow_origins = cors_options.get("allow_origins", [])
    assert "*" not in allow_origins
    assert any("127.0.0.1" in o or "localhost" in o for o in allow_origins)
