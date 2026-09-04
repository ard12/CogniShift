"""Pytest test fixtures for CogniShift."""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# Configure disposable persistence before importing any CogniShift module.
# This prevents regression and adversarial tests from contaminating the live
# demo database, vector store, uploads, or credential store.
TEST_RUNTIME_ROOT = Path(tempfile.mkdtemp(prefix="cognishift-pytest-"))
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
VISION_FIXTURES = REPOSITORY_ROOT / "data" / "vision_test"
if VISION_FIXTURES.exists():
    shutil.copytree(VISION_FIXTURES, TEST_RUNTIME_ROOT / "vision_test")
os.environ["DATA_DIR"] = str(TEST_RUNTIME_ROOT)
os.environ["DATABASE_PATH"] = str(TEST_RUNTIME_ROOT / "cognishift.db")
os.environ["CHROMA_PATH"] = str(TEST_RUNTIME_ROOT / "chroma")
os.environ["UPLOAD_DIR"] = str(TEST_RUNTIME_ROOT / "uploads")
os.environ["AUTH_STORE_PATH"] = str(TEST_RUNTIME_ROOT / "private" / "auth_store.json")

from cognishift.app.config import settings
from cognishift.app.core.auth import (
    EPHEMERAL_DEMO_SESSIONS,
    LOCAL_CREDENTIAL_STORE,
    User,
    register_local_credential,
)

TEST_OPERATOR_TOKEN = "test-token-operator-998"
TEST_SUPERVISOR_TOKEN = "test-token-supervisor-554"
TEST_ADMIN_TOKEN = "test-token-admin-112"
TEST_TENANT2_TOKEN = "test-token-tenant2-334"
TEST_REVOKED_TOKEN = "test-token-revoked-000"


def pytest_sessionfinish(session, exitstatus):
    """Remove the isolated test persistence tree after the test session."""
    shutil.rmtree(TEST_RUNTIME_ROOT, ignore_errors=True)

@pytest.fixture(autouse=True)
def setup_test_auth_credentials(tmp_path, monkeypatch):
    """Provision isolated test credentials into memory during tests only."""
    monkeypatch.setattr(settings, "auth_store_path", tmp_path / "test_auth_store.json")
    LOCAL_CREDENTIAL_STORE.clear()
    EPHEMERAL_DEMO_SESSIONS.clear()
    register_local_credential(
        TEST_OPERATOR_TOKEN,
        User(user_id="operator_sam", role="operator", allowed_workspace_ids=[1])
    )
    register_local_credential(
        TEST_SUPERVISOR_TOKEN,
        User(user_id="supervisor_jane", role="supervisor", allowed_workspace_ids=[1, 2])
    )
    register_local_credential(
        TEST_ADMIN_TOKEN,
        User(user_id="admin_rohit", role="administrator", allowed_workspace_ids=[1, 2, 3])
    )
    register_local_credential(
        TEST_TENANT2_TOKEN,
        User(user_id="operator_tenant2", role="operator", allowed_workspace_ids=[2])
    )
    register_local_credential(
        TEST_REVOKED_TOKEN,
        User(user_id="revoked_operator", role="operator", allowed_workspace_ids=[1]),
        enabled=False
    )
    yield
    LOCAL_CREDENTIAL_STORE.clear()
    EPHEMERAL_DEMO_SESSIONS.clear()
