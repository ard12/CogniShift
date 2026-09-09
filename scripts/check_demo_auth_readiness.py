"""Safe, secret-free readiness diagnostics for CogniShift local authentication."""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from cognishift.app.config import settings


EXPECTED_IDENTITIES = {
    "operator_sam": "Operator",
    "supervisor_jane": "Supervisor",
    "admin_rohit": "Administrator",
}


def main() -> int:
    print("COGNISHIFT AUTH READINESS\n")
    passed = True
    store_path = settings.auth_store_path.resolve()
    print(f"[OK] Credential store resolved:\n     {store_path}")

    identities = set()
    try:
        data = json.loads(store_path.read_text(encoding="utf-8"))
        identities = {record.get("user_id") for record in data.get("users", [])}
    except (OSError, ValueError, TypeError) as exc:
        passed = False
        print(f"[FAIL] Credential store could not be read: {type(exc).__name__}")

    for user_id, label in EXPECTED_IDENTITIES.items():
        found = user_id in identities
        passed = passed and found
        print(f"[{'OK' if found else 'FAIL'}] {label} identity {'present' if found else 'missing'}")

    canonical = (ROOT_DIR / "data" / "private" / "auth_store.json").resolve()
    same_store = store_path == canonical or "AUTH_STORE_PATH" in __import__("os").environ
    passed = passed and same_store
    print(f"[{'OK' if same_store else 'FAIL'}] Server configuration uses resolved store")

    auth_api_source = (ROOT_DIR / "src" / "cognishift" / "app" / "api" / "auth.py").read_text(encoding="utf-8")
    capability = 'post("/demo-session"' in auth_api_source and "_is_loopback" in auth_api_source
    passed = passed and capability
    print(f"[{'OK' if capability else 'FAIL'}] Local-only demo session capability installed")
    print(f"[{'OK' if settings.cognishift_demo_mode else 'INFO'}] Demo session mode "
          f"{'enabled' if settings.cognishift_demo_mode else 'disabled (secure default)' }")

    print("\nRESULT:")
    print("AUTH READY" if passed else "AUTH NOT READY")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
