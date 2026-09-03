"""Pytest test fixtures for CogniShift."""
import pytest
from cognishift.app.core.auth import User, register_local_credential, LOCAL_CREDENTIAL_STORE

TEST_OPERATOR_TOKEN = "test-token-operator-998"
TEST_SUPERVISOR_TOKEN = "test-token-supervisor-554"
TEST_ADMIN_TOKEN = "test-token-admin-112"
TEST_TENANT2_TOKEN = "test-token-tenant2-334"
TEST_REVOKED_TOKEN = "test-token-revoked-000"

@pytest.fixture(autouse=True)
def setup_test_auth_credentials():
    """Provision isolated test credentials into memory during tests only."""
    LOCAL_CREDENTIAL_STORE.clear()
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
