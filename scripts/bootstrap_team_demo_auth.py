#!/usr/bin/env python3
"""Bootstrap authentication tokens for the 6 demonstration personas into auth_store.json."""
import hashlib
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import argparse
import secrets

TEAM_PERSONAS = [
    {
        "user_id": "sitanshu",
        "role": "administrator",
        "allowed_workspace_ids": [1, 2, 3],
        "name": "Sitanshu (Host Admin)",
    },
    {
        "user_id": "zara",
        "role": "supervisor",
        "allowed_workspace_ids": [1, 2],
        "name": "Zara (Four-Eyes Supervisor 1)",
    },
    {
        "user_id": "rakshita",
        "role": "supervisor",
        "allowed_workspace_ids": [1, 2],
        "name": "Rakshita (Four-Eyes Supervisor 2)",
    },
    {
        "user_id": "aryan",
        "role": "operator",
        "allowed_workspace_ids": [1],
        "name": "Aryan (Plant Operator 1)",
    },
    {
        "user_id": "vicky",
        "role": "supervisor",
        "allowed_workspace_ids": [1, 2],
        "name": "Vicky (Four-Eyes Supervisor 3)",
    },
    {
        "user_id": "rohit",
        "role": "operator",
        "allowed_workspace_ids": [1],
        "name": "Rohit (Untrusted Terminal Demo)",
    },
]

# Known legacy demonstration token hashes permanently revoked and purged
LEGACY_REVOKED_HASHES = {
    "d5ad77186cfd52153096bcafddc5567d8ba6f59d43408cac877662d7c010a77f",  # legacy rohit
    "3bb8c04b9a475f48470cbff92a643b58932986d11e52dd0714eeddc600bc3169",  # legacy sitanshu
    "8ed8779ef598814f34e1d633342f5086db5289572efea7d14de365d29fa41d0e",  # legacy zara
    "da9e173beae5642d997a3a9fbff4a1936e3ae3eef1952e462d7ffbf58913ba58",  # legacy rakshita
    "36a43872c0c7a87e3573c52a03eef591bead0175b9f9ec046db415174ae53d10",  # legacy aryan
    "9eec9ebae63138b67104ae32f0c72c219602e1b1d1aa09ee9306b3bc4f1a6f81",  # legacy vicky
}


def generate_persona_token(user_id: str) -> str:
    """Generate a high-entropy, cryptographically random token for a team persona."""
    entropy = secrets.token_urlsafe(24)
    return f"cs_{user_id}_{entropy}"


def parse_existing_summary(summary_path: Path) -> dict:
    """Extract previously generated tokens from local summary file if present."""
    if not summary_path.exists():
        return {}
    content = summary_path.read_text(encoding="utf-8")
    tokens = {}
    current_user = None
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("User ID:"):
            current_user = line.split(":", 1)[1].strip()
        elif line.startswith("Token:") and current_user:
            tok = line.split(":", 1)[1].strip()
            thash = hashlib.sha256(tok.encode("utf-8")).hexdigest()
            if thash not in LEGACY_REVOKED_HASHES and len(tok) >= 20:
                tokens[current_user] = tok
            current_user = None
    return tokens


def main():
    parser = argparse.ArgumentParser(description="Bootstrap local team auth credentials.")
    parser.add_argument("--rotate", action="store_true", help="Rotate all team tokens and regenerate fresh secrets.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    private_dir = root / "data" / "private"
    private_dir.mkdir(parents=True, exist_ok=True)

    auth_store_file = private_dir / "auth_store.json"
    summary_file = private_dir / "team_tokens_summary.txt"

    existing_tokens = {} if args.rotate else parse_existing_summary(summary_file)

    # Legacy revoked token hashes to purge
    revoked_hashes = set(LEGACY_REVOKED_HASHES)

    assigned_credentials = []
    summary_lines = [
        "=== COGNISHIFT TEAM DEMO TOKENS ===",
        "CONFIDENTIAL — LOCAL SOVEREIGN SECRETS ONLY",
        "DO NOT COMMIT TO GIT OR EXPOSE TO EXTERNAL NETWORKS",
        "",
    ]

    for persona in TEAM_PERSONAS:
        u_id = persona["user_id"]
        token = existing_tokens.get(u_id)
        if not token:
            token = generate_persona_token(u_id)

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        assigned_credentials.append({
            "credential_hash": token_hash,
            "user_id": u_id,
            "role": persona["role"],
            "allowed_workspace_ids": persona["allowed_workspace_ids"],
            "enabled": True,
        })

        summary_lines.append(f"Persona:    {persona['name']}")
        summary_lines.append(f"User ID:    {u_id}")
        summary_lines.append(f"Role:       {persona['role']}")
        summary_lines.append(f"Token:      {token}")
        summary_lines.append(f"Workspaces: {persona['allowed_workspace_ids']}")
        summary_lines.append("-" * 44)

    # Read existing auth store and purge revoked/stale hashes
    preserved_records = {}
    if auth_store_file.exists():
        try:
            data = json.loads(auth_store_file.read_text(encoding="utf-8"))
            for u in data.get("users", []):
                h = u.get("credential_hash")
                if h and h not in revoked_hashes:
                    preserved_records[h] = u
        except Exception:
            pass

    # Remove any old persona hashes for these specific team users to avoid duplicates
    team_uids = {p["user_id"] for p in TEAM_PERSONAS}
    preserved_records = {
        h: u for h, u in preserved_records.items()
        if u.get("user_id") not in team_uids
    }

    # Add the current assigned credentials
    for cred in assigned_credentials:
        preserved_records[cred["credential_hash"]] = cred

    auth_store_file.write_text(
        json.dumps(
            {
                "$comment": "CogniShift Local Sovereign Credential Store. Excluded from Git.",
                "users": list(preserved_records.values()),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    summary_file.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    action = "Rotated" if args.rotate else "Provisioned"
    print(f"[SUCCESS] {action} {len(assigned_credentials)} team credentials.")
    print(f"[SUCCESS] Stored hashes in {auth_store_file}")
    print(f"[SUCCESS] Plaintext tokens written strictly to gitignored {summary_file}")


if __name__ == "__main__":
    main()
