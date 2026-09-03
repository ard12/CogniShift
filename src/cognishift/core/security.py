"""Canonical Safe Workspace Path Resolver for CogniShift."""
import logging
from pathlib import Path
from typing import Optional

from cognishift.app.config import settings

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Raised when a path access violates workspace security boundaries."""
    pass


def get_workspace_root(workspace_id: int) -> Path:
    """Get canonical directory root for a workspace, ensuring it exists."""
    root = (settings.data_dir / "workspaces" / str(workspace_id)).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_workspace_path(
    workspace_id: int,
    relative_path: str,
    purpose: str = "read",
    allow_create_parent: bool = False
) -> Path:
    """
    Resolve and validate a relative path within a specific workspace.
    
    Security Guarantees:
    1. Workspace root is canonical and server-controlled.
    2. Rejects any absolute paths.
    3. Rejects null-bytes or traversal patterns.
    4. Resolves realpath and verifies destination is strictly within workspace root.
    5. Disallows symlink breakouts.
    
    Args:
        workspace_id: Target workspace ID.
        relative_path: Relative path inside the workspace.
        purpose: 'read', 'write', or 'delete'.
        allow_create_parent: If True, creates parent directories for write operations.
        
    Returns:
        Resolved Path object strictly contained inside the workspace.
        
    Raises:
        SecurityError: If any path boundary rule is violated.
    """
    if not relative_path:
        raise SecurityError("Path cannot be empty.")
        
    # Reject null bytes
    if "\x00" in relative_path:
        raise SecurityError("Null bytes in path are forbidden.")
        
    from urllib.parse import unquote
    # URL decode to catch %2e%2e traversal attempts
    decoded = unquote(relative_path)
    if ".." in decoded:
        logger.warning(
            f"SECURITY ALERT: Traversal token '..' detected in '{relative_path}' for workspace {workspace_id}"
        )
        raise SecurityError(f"Directory traversal tokens forbidden: '{relative_path}'")

    raw_path = Path(relative_path)
    
    # 1. Reject absolute paths (covers C:\, /etc, \Windows, and UNC paths)
    if (
        raw_path.is_absolute() 
        or raw_path.drive 
        or relative_path.startswith("/") 
        or relative_path.startswith("\\")
        or decoded.startswith("/")
        or decoded.startswith("\\")
    ):
        logger.warning(
            f"SECURITY ALERT: Absolute path rejected: '{relative_path}' in workspace {workspace_id}"
        )
        raise SecurityError(f"Absolute paths are forbidden: '{relative_path}'")
        
    # 2. Reject obvious traversal tokens before resolution
    parts = raw_path.parts
    if ".." in parts:
        logger.warning(
            f"SECURITY ALERT: Traversal token '..' detected: '{relative_path}' in workspace {workspace_id}"
        )
        raise SecurityError(f"Directory traversal tokens forbidden: '{relative_path}'")
        
    # 3. Canonical resolution
    workspace_root = get_workspace_root(workspace_id)
    resolved_target = (workspace_root / raw_path).resolve()
    
    # 4. Strict boundary check: target must be inside workspace_root
    try:
        resolved_target.relative_to(workspace_root)
    except ValueError:
        logger.critical(
            f"SECURITY ALERT: Path traversal escape attempt! "
            f"Workspace: {workspace_id}, Target: '{resolved_target}', Root: '{workspace_root}'"
        )
        raise SecurityError(
            f"Access denied: Path '{relative_path}' resolves outside workspace boundary."
        )
        
    # 5. Purpose-specific checks
    if purpose == "read" and not resolved_target.exists():
        raise FileNotFoundError(f"File not found in workspace #{workspace_id}: '{relative_path}'")
        
    if purpose == "write" and allow_create_parent:
        resolved_target.parent.mkdir(parents=True, exist_ok=True)
        
    return resolved_target
