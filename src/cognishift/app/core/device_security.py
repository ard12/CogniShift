"""Local trusted-device challenge/response using browser-held ECDSA P-256 keys."""
import base64
import hashlib
import json
import secrets
import time
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
"""Local trusted-device challenge/response using browser-held ECDSA P-256 keys."""
import base64
import hashlib
import json
import secrets
import time
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.hashes import SHA256

from cognishift.app.config import settings
from cognishift.app.db.database import get_db


DEVICE_SESSIONS: Dict[str, tuple[str, str, str, float]] = {}


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def canonical_public_jwk(jwk: Dict[str, Any]) -> str:
    if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256" or not jwk.get("x") or not jwk.get("y"):
        raise ValueError("Device key must be an ECDSA P-256 public key.")
    return json.dumps({"crv": "P-256", "kty": "EC", "x": jwk["x"], "y": jwk["y"]}, sort_keys=True, separators=(",", ":"))


def key_fingerprint(jwk: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_public_jwk(jwk).encode()).hexdigest()


async def record_device_audit(user_id: str, action: str, device_id: str, result: str, details: str) -> None:
    async with get_db() as db:
        await db.execute(
            "INSERT INTO audit_events (actor_id, action, resource_type, details, result) VALUES (?, ?, 'trusted_device', ?, ?)",
            (user_id, action, f"device_id={device_id}; {details}", result),
        )
        await db.commit()


async def restore_active_device_sessions() -> None:
    """Load valid unexpired sessions from database into process memory cache on startup."""
    now = time.time()
    async with get_db() as db:
        # Purge expired sessions
        await db.execute("DELETE FROM active_device_sessions WHERE expires_at <= ?", (now,))
        await db.commit()

        rows = await (await db.execute(
            "SELECT session_hash, user_id, device_id, key_fingerprint, expires_at FROM active_device_sessions WHERE expires_at > ?",
            (now,)
        )).fetchall()
        for row in rows:
            DEVICE_SESSIONS[row["session_hash"]] = (
                row["user_id"],
                row["device_id"],
                row["key_fingerprint"],
                float(row["expires_at"]),
            )


async def begin_challenge(
    user_id: str,
    role: str,
    device_id: str,
    display_name: str,
    public_jwk: Dict[str, Any],
    is_loopback: bool = False,
    client_ip: Optional[str] = None,
) -> Dict[str, Any]:
    canonical = canonical_public_jwk(public_jwk)
    fingerprint = key_fingerprint(public_jwk)
    async with get_db() as db:
        row = await (await db.execute(
            "SELECT * FROM trusted_devices WHERE device_id = ? AND user_id = ?",
            (device_id, user_id),
        )).fetchone()
        approved_count = (await (await db.execute(
            "SELECT count(*) AS n FROM trusted_devices WHERE status = 'approved'"
        )).fetchone())["n"]

        # Loopback-only bootstrap for the very first administrator
        if not row and role == "administrator" and approved_count == 0 and is_loopback:
            await db.execute(
                "INSERT INTO trusted_devices (device_id, user_id, display_name, public_key_jwk, key_fingerprint, status, approved_by, approved_at, last_ip) "
                "VALUES (?, ?, ?, ?, ?, 'approved', ?, CURRENT_TIMESTAMP, ?)",
                (device_id, user_id, display_name[:100], canonical, fingerprint, user_id, client_ip),
            )
            await db.execute(
                "INSERT INTO audit_events (actor_id, action, resource_type, details, result) "
                "VALUES (?, 'trusted_device_bootstrap', 'trusted_device', ?, 'success')",
                (user_id, f"First trusted administrator device bootstrapped via loopback; device_id={device_id}; fingerprint={fingerprint}; ip={client_ip}"),
            )
            await db.commit()
            row = await (await db.execute(
                "SELECT * FROM trusted_devices WHERE device_id = ? AND user_id = ?",
                (device_id, user_id),
            )).fetchone()
        elif not row:
            # New device - requires administrator approval
            bootstrap_denied = (role == "administrator" and approved_count == 0 and not is_loopback)
            detail_msg = (
                f"Remote administrator bootstrap denied without loopback; device_id={device_id}; ip={client_ip}"
                if bootstrap_denied
                else f"Unknown device; credentials verified; administrator approval required; device_id={device_id}; fingerprint={fingerprint}; ip={client_ip}"
            )
            await db.execute(
                "INSERT INTO trusted_devices (device_id, user_id, display_name, public_key_jwk, key_fingerprint, status, last_ip) "
                "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                (device_id, user_id, display_name[:100], canonical, fingerprint, client_ip),
            )
            await db.execute(
                "INSERT INTO audit_events (actor_id, action, resource_type, details, result) "
                "VALUES (?, 'device_verification_failed', 'trusted_device', ?, 'blocked')",
                (user_id, detail_msg),
            )
            await db.commit()
            return {"status": "unknown_device"}
        elif row["status"] in ("blocked", "revoked"):
            await db.execute(
                "INSERT INTO audit_events (actor_id, action, resource_type, details, result) "
                "VALUES (?, 'device_verification_failed', 'trusted_device', ?, 'blocked')",
                (user_id, f"Device status is {row['status']}; device_id={device_id}; ip={client_ip}"),
            )
            await db.commit()
            return {"status": row["status"]}
        elif row["status"] != "approved" or row["key_fingerprint"] != fingerprint:
            if client_ip and ("last_ip" in row.keys() and row["last_ip"] != client_ip):
                await db.execute(
                    "UPDATE trusted_devices SET last_ip = ? WHERE device_id = ? AND user_id = ?",
                    (client_ip, device_id, user_id),
                )
            await db.execute(
                "INSERT INTO audit_events (actor_id, action, resource_type, details, result) "
                "VALUES (?, 'device_verification_failed', 'trusted_device', ?, 'blocked')",
                (user_id, f"Device not approved or public key mismatch; status={row['status']}; device_id={device_id}; ip={client_ip}"),
            )
            await db.commit()
            return {"status": "unknown_device"}

        # Device is approved and fingerprint matches: issue challenge
        if client_ip:
            await db.execute(
                "UPDATE trusted_devices SET last_ip = ? WHERE device_id = ? AND user_id = ?",
                (client_ip, device_id, user_id),
            )

        challenge_id = secrets.token_urlsafe(24)
        challenge = secrets.token_bytes(32)
        challenge_b64 = base64.urlsafe_b64encode(challenge).decode().rstrip("=")
        await db.execute(
            "INSERT INTO device_challenges (challenge_id, device_id, user_id, key_fingerprint, challenge_b64, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (challenge_id, device_id, user_id, fingerprint, challenge_b64, time.time() + settings.device_challenge_ttl_seconds),
        )
        await db.commit()
        return {"status": "challenge", "challenge_id": challenge_id, "challenge": challenge_b64}


async def verify_challenge(user_id: str, device_id: str, challenge_id: str, signature_b64: str) -> str:
    async with get_db() as db:
        challenge = await (await db.execute(
            "SELECT * FROM device_challenges WHERE challenge_id=? AND device_id=? AND user_id=? AND used=0",
            (challenge_id, device_id, user_id),
        )).fetchone()
        device = await (await db.execute(
            "SELECT * FROM trusted_devices WHERE device_id=? AND user_id=? AND status='approved'",
            (device_id, user_id),
        )).fetchone()
        if not challenge or not device or challenge["expires_at"] < time.time():
            raise ValueError("Device challenge is invalid or expired.")

        # Bind challenge fingerprint to device fingerprint if recorded
        if "key_fingerprint" in challenge.keys() and challenge["key_fingerprint"] and challenge["key_fingerprint"] != device["key_fingerprint"]:
            raise ValueError("Challenge key fingerprint does not match approved device.")

        jwk = json.loads(device["public_key_jwk"])
        public_key = ec.EllipticCurvePublicNumbers(
            int.from_bytes(_b64url_decode(jwk["x"]), "big"),
            int.from_bytes(_b64url_decode(jwk["y"]), "big"),
            ec.SECP256R1(),
        ).public_key()
        raw_sig = _b64url_decode(signature_b64)
        if len(raw_sig) == 64:
            raw_sig = encode_dss_signature(int.from_bytes(raw_sig[:32], "big"), int.from_bytes(raw_sig[32:], "big"))
        try:
            public_key.verify(raw_sig, _b64url_decode(challenge["challenge_b64"]), ec.ECDSA(SHA256()))
        except InvalidSignature as exc:
            await db.execute(
                "INSERT INTO audit_events (actor_id, action, resource_type, details, result) "
                "VALUES (?, 'device_verification_failed', 'trusted_device', ?, 'blocked')",
                (user_id, f"device_id={device_id}; Challenge signature invalid"),
            )
            await db.commit()
            raise ValueError("Device signature verification failed.") from exc

        await db.execute("UPDATE device_challenges SET used=1 WHERE challenge_id=?", (challenge_id,))
        await db.execute(
            "UPDATE trusted_devices SET last_verified_at=CURRENT_TIMESTAMP WHERE device_id=? AND user_id=?",
            (device_id, user_id),
        )
        await db.execute(
            "INSERT INTO audit_events (actor_id, action, resource_type, details, result) VALUES (?, 'device_verified', 'trusted_device', ?, 'success')",
            (user_id, f"Cryptographic challenge verified; device_id={device_id}"),
        )

        raw_session = secrets.token_urlsafe(32)
        session_hash = hashlib.sha256(raw_session.encode()).hexdigest()
        expires_at = time.time() + settings.device_session_ttl_seconds

        # Persist session to DB table for multi-process / restart durability
        await db.execute(
            "INSERT INTO active_device_sessions (session_hash, user_id, device_id, key_fingerprint, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_hash, user_id, device_id, device["key_fingerprint"], expires_at),
        )
        await db.commit()

    # Update in-memory cache
    DEVICE_SESSIONS[session_hash] = (user_id, device_id, device["key_fingerprint"], expires_at)
    return raw_session


def validate_device_session(raw_session: str, user_id: str) -> Optional[str]:
    if not raw_session:
        return None
    session_hash = hashlib.sha256(raw_session.encode()).hexdigest()
    record = DEVICE_SESSIONS.get(session_hash)
    if not record:
        return None
    rec_user_id, device_id, _rec_fingerprint, expires_at = record
    if rec_user_id != user_id or expires_at <= time.time():
        DEVICE_SESSIONS.pop(session_hash, None)
        return None
    return device_id


async def approve_device(device_id: str, user_id: str, approved_by: str) -> bool:
    """Approve a pending device for a specific user."""
    async with get_db() as db:
        res = await db.execute(
            "UPDATE trusted_devices SET status='approved', approved_by=?, approved_at=CURRENT_TIMESTAMP, revoked_at=NULL, blocked_at=NULL "
            "WHERE device_id=? AND user_id=?",
            (approved_by, device_id, user_id),
        )
        if res.rowcount == 0:
            return False
        await db.execute(
            "INSERT INTO audit_events (actor_id, action, resource_type, details, result) "
            "VALUES (?, 'trusted_device_approved', 'trusted_device', ?, 'success')",
            (approved_by, f"Approved device_id={device_id} for user={user_id}"),
        )
        await db.commit()
    return True


async def revoke_device(device_id: str, user_id: Optional[str] = None, actor_id: str = "administrator") -> None:
    """Revoke a trusted device and immediately terminate active sessions."""
    async with get_db() as db:
        if user_id:
            await db.execute(
                "UPDATE trusted_devices SET status='revoked', revoked_at=CURRENT_TIMESTAMP WHERE device_id=? AND user_id=?",
                (device_id, user_id),
            )
            await db.execute("DELETE FROM active_device_sessions WHERE device_id=? AND user_id=?", (device_id, user_id))
        else:
            await db.execute(
                "UPDATE trusted_devices SET status='revoked', revoked_at=CURRENT_TIMESTAMP WHERE device_id=?",
                (device_id,),
            )
            await db.execute("DELETE FROM active_device_sessions WHERE device_id=?", (device_id,))

        await db.execute(
            "INSERT INTO audit_events (actor_id, action, resource_type, details, result) "
            "VALUES (?, 'trusted_device_revoked', 'trusted_device', ?, 'success')",
            (actor_id, f"Revoked device_id={device_id}" + (f" user={user_id}" if user_id else "")),
        )
        await db.commit()

    # Evict matching sessions from in-memory cache
    to_remove = [
        s_hash for s_hash, data in DEVICE_SESSIONS.items()
        if data[1] == device_id and (user_id is None or data[0] == user_id)
    ]
    for s_hash in to_remove:
        DEVICE_SESSIONS.pop(s_hash, None)


async def block_device(device_id: str, user_id: Optional[str] = None, actor_id: str = "administrator") -> None:
    """Block a device completely and immediately terminate active sessions."""
    async with get_db() as db:
        if user_id:
            await db.execute(
                "UPDATE trusted_devices SET status='blocked', blocked_at=CURRENT_TIMESTAMP WHERE device_id=? AND user_id=?",
                (device_id, user_id),
            )
            await db.execute("DELETE FROM active_device_sessions WHERE device_id=? AND user_id=?", (device_id, user_id))
        else:
            await db.execute(
                "UPDATE trusted_devices SET status='blocked', blocked_at=CURRENT_TIMESTAMP WHERE device_id=?",
                (device_id,),
            )
            await db.execute("DELETE FROM active_device_sessions WHERE device_id=?", (device_id,))

        await db.execute(
            "INSERT INTO audit_events (actor_id, action, resource_type, details, result) "
            "VALUES (?, 'trusted_device_blocked', 'trusted_device', ?, 'success')",
            (actor_id, f"Blocked device_id={device_id}" + (f" user={user_id}" if user_id else "")),
        )
        await db.commit()

    # Evict matching sessions from in-memory cache
    to_remove = [
        s_hash for s_hash, data in DEVICE_SESSIONS.items()
        if data[1] == device_id and (user_id is None or data[0] == user_id)
    ]
    for s_hash in to_remove:
        DEVICE_SESSIONS.pop(s_hash, None)
