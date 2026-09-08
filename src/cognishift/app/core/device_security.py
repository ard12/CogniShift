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


DEVICE_SESSIONS: Dict[str, tuple[str, str, float]] = {}


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


async def begin_challenge(user_id: str, role: str, device_id: str, display_name: str, public_jwk: Dict[str, Any]) -> Dict[str, Any]:
    canonical = canonical_public_jwk(public_jwk)
    fingerprint = key_fingerprint(public_jwk)
    async with get_db() as db:
        row = await (await db.execute("SELECT * FROM trusted_devices WHERE device_id = ? AND user_id = ?", (device_id, user_id))).fetchone()
        approved_count = (await (await db.execute("SELECT count(*) AS n FROM trusted_devices WHERE status = 'approved'")).fetchone())["n"]
        if not row and role == "administrator" and approved_count == 0:
            await db.execute(
                "INSERT INTO trusted_devices (device_id,user_id,display_name,public_key_jwk,key_fingerprint,status,approved_by,approved_at) VALUES (?,?,?,?,?,'approved',?,CURRENT_TIMESTAMP)",
                (device_id, user_id, display_name[:100], canonical, fingerprint, user_id),
            )
            await db.execute(
                "INSERT INTO audit_events (actor_id,action,resource_type,details,result) VALUES (?,'trusted_device_bootstrap','trusted_device',?,'success')",
                (user_id, f"First trusted administrator device registered; device_id={device_id}; fingerprint={fingerprint}"),
            )
            await db.commit()
            row = await (await db.execute("SELECT * FROM trusted_devices WHERE device_id = ?", (device_id,))).fetchone()
        elif not row:
            await db.execute(
                "INSERT INTO trusted_devices (device_id,user_id,display_name,public_key_jwk,key_fingerprint,status) VALUES (?,?,?,?,?,'pending')",
                (device_id, user_id, display_name[:100], canonical, fingerprint),
            )
            await db.execute(
                "INSERT INTO audit_events (actor_id,action,resource_type,details,result) VALUES (?,'device_verification_failed','trusted_device',?,'blocked')",
                (user_id, f"Unknown device; credentials verified; administrator approval required; device_id={device_id}; fingerprint={fingerprint}"),
            )
            await db.commit()
            return {"status": "unknown_device"}
        elif row["status"] != "approved" or row["key_fingerprint"] != fingerprint:
            await db.execute(
                "INSERT INTO audit_events (actor_id,action,resource_type,details,result) VALUES (?,'device_verification_failed','trusted_device',?,'blocked')",
                (user_id, f"Device not approved or public key mismatch; device_id={device_id}"),
            )
            await db.commit()
            return {"status": "unknown_device"}

        challenge_id = secrets.token_urlsafe(24)
        challenge = secrets.token_bytes(32)
        challenge_b64 = base64.urlsafe_b64encode(challenge).decode().rstrip("=")
        await db.execute(
            "INSERT INTO device_challenges (challenge_id,device_id,user_id,challenge_b64,expires_at) VALUES (?,?,?,?,?)",
            (challenge_id, device_id, user_id, challenge_b64, time.time() + settings.device_challenge_ttl_seconds),
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
                "INSERT INTO audit_events (actor_id,action,resource_type,details,result) "
                "VALUES (?,'device_verification_failed','trusted_device',?,'blocked')",
                (user_id, f"device_id={device_id}; Challenge signature invalid"),
            )
            await db.commit()
            raise ValueError("Device signature verification failed.") from exc
        await db.execute("UPDATE device_challenges SET used=1 WHERE challenge_id=?", (challenge_id,))
        await db.execute("UPDATE trusted_devices SET last_verified_at=CURRENT_TIMESTAMP WHERE device_id=?", (device_id,))
        await db.execute(
            "INSERT INTO audit_events (actor_id,action,resource_type,details,result) VALUES (?,'device_verified','trusted_device',?,'success')",
            (user_id, f"Cryptographic challenge verified; device_id={device_id}"),
        )
        await db.commit()
    raw_session = secrets.token_urlsafe(32)
    DEVICE_SESSIONS[hashlib.sha256(raw_session.encode()).hexdigest()] = (
        user_id, device_id, time.time() + settings.device_session_ttl_seconds,
    )
    return raw_session


def validate_device_session(raw_session: str, user_id: str) -> Optional[str]:
    if not raw_session:
        return None
    record = DEVICE_SESSIONS.get(hashlib.sha256(raw_session.encode()).hexdigest())
    if not record or record[0] != user_id or record[2] <= time.time():
        return None
    return record[1]
