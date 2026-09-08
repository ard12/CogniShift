#!/usr/bin/env python3
"""Bootstrap authentication tokens for the 6 demonstration personas into auth_store.json."""
import hashlib
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

TEAM_CREDENTIALS = [
    {
        "user_id": "sitanshu",
        "role": "administrator",
        "token": "cs_sitanshu_admin_token_2026_sih",
        "allowed_workspace_ids": [1, 2, 3],
        "name": "Sitanshu (Host Admin)",
    },
    {
        "user_id": "zara",
        "role": "supervisor",
        "token": "cs_zara_supervisor_token_2026_sih",
        "allowed_workspace_ids": [1, 2],
        "name": "Zara (Four-Eyes Supervisor 1)",
    },
    {
        "user_id": "rakshita",
        "role": "supervisor",
        "token": "cs_rakshita_supervisor_token_2026_sih",
        "allowed_workspace_ids": [1, 2],
        "name": "Rakshita (Four-Eyes Supervisor 2)",
    },
    {
        "user_id": "aryan",
        "role": "operator",
        "token": "cs_aryan_operator_token_2026_sih",
        "allowed_workspace_ids": [1],
        "name": "Aryan (Plant Operator 1)",
    },
    {
        "user_id": "vicky",
        "role": "operator",
        "token": "cs_vicky_operator_token_2026_sih",
        "allowed_workspace_ids": [1],
        "name": "Vicky (Plant Operator 2)",
    },
    {
        "user_id": "rohit",
        "role": "operator",
        "token": "cs_rohit_operator_token_2026_sih",
        "allowed_workspace_ids": [1],
        "name": "Rohit (Untrusted Terminal Demo)",
    },
]


def main():
    root = Path(__file__).resolve().parent.parent
    auth_store_file = root / "data" / "private" / "auth_store.json"
    auth_store_file.parent.mkdir(parents=True, exist_ok=True)

    existing_data = {"$comment": "CogniShift Local Sovereign Credential Store. Excluded from Git.", "users": []}
    if auth_store_file.exists():
        try:
            existing_data = json.loads(auth_store_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    existing_users = {u["credential_hash"]: u for u in existing_data.get("users", [])}

    summary_lines = ["=== COGNISHIFT TEAM DEMO TOKENS ===", ""]
    for cred in TEAM_CREDENTIALS:
        raw_token = cred["token"]
        h = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        existing_users[h] = {
            "credential_hash": h,
            "user_id": cred["user_id"],
            "role": cred["role"],
            "allowed_workspace_ids": cred["allowed_workspace_ids"],
            "enabled": True,
        }
        summary_lines.append(f"Persona:  {cred['name']}")
        summary_lines.append(f"User ID:  {cred['user_id']}")
        summary_lines.append(f"Role:     {cred['role']}")
        summary_lines.append(f"Token:    {raw_token}")
        summary_lines.append(f"Workspaces: {cred['allowed_workspace_ids']}")
        summary_lines.append("-" * 40)

    auth_store_file.write_text(
        json.dumps({"$comment": "CogniShift Local Sovereign Credential Store. Excluded from Git.", "users": list(existing_users.values())}, indent=2),
        encoding="utf-8",
    )

    summary_file = root / "data" / "private" / "team_tokens_summary.txt"
    summary_file.write_text("\n".join(summary_lines), encoding="utf-8")

    print(f"[SUCCESS] Updated {auth_store_file} with {len(TEAM_CREDENTIALS)} team credentials.")
    print(f"[SUCCESS] Wrote token summary to {summary_file}")


if __name__ == "__main__":
    main()
