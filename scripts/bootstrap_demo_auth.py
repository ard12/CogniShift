"""Bootstrap local demonstration credentials for CogniShift.

Generates local cryptographic credentials, writes the hashed records
into data/private/auth_store.json (excluded from git), and displays the
one-time raw tokens to the administrator.
"""
import sys
import secrets
import argparse
from pathlib import Path

# Ensure src is in python path
src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from cognishift.app.core.auth import User, register_local_credential, save_credential_store
from cognishift.app.config import settings

def main():
    parser = argparse.ArgumentParser(description="Bootstrap local demonstration credentials.")
    parser.add_argument("--deterministic", action="store_true", help="Use fixed test keys for reproducible test runs")
    args = parser.parse_args()

    store_path = settings.auth_store_path
    print(f"Provisioning sovereign credentials to: {store_path}")

    if args.deterministic:
        tokens = {
            "operator": "test-key-operator-48291",
            "supervisor": "test-key-supervisor-71024",
            "administrator": "test-key-admin-99015",
            "tenant2": "test-key-tenant2-10842"
        }
    else:
        tokens = {
            "operator": f"cog_op_{secrets.token_urlsafe(24)}",
            "supervisor": f"cog_sup_{secrets.token_urlsafe(24)}",
            "administrator": f"cog_adm_{secrets.token_urlsafe(24)}",
            "tenant2": f"cog_op2_{secrets.token_urlsafe(24)}"
        }

    register_local_credential(tokens["operator"], User(user_id="operator_sam", role="operator", allowed_workspace_ids=[1]))
    register_local_credential(tokens["supervisor"], User(user_id="supervisor_jane", role="supervisor", allowed_workspace_ids=[1, 2]))
    register_local_credential(tokens["administrator"], User(user_id="admin_rohit", role="administrator", allowed_workspace_ids=[1, 2, 3]))
    register_local_credential(tokens["tenant2"], User(user_id="operator_tenant2", role="operator", allowed_workspace_ids=[2]))

    save_credential_store(store_path)

    print("
" + "="*60)
    print("COGNISHIFT SOVEREIGN LOCAL CREDENTIALS GENERATED")
    print("WARNING: Store these tokens securely. They will NOT be displayed again.")
    print("="*60)
    for role, tok in tokens.items():
        print(f"  {role.upper():<15}: {tok}")
    print("="*60 + "
")

if __name__ == "__main__":
    main()
