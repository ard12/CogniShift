"""Tests for Judge Presentation Reset Engine."""
import pytest
import aiosqlite
from pathlib import Path

from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from scripts.reset_team_demo_state import reset_demo_state


@pytest.mark.asyncio
async def test_judge_reset_dry_run_preserves_everything():
    """Verify dry-run mode inspects state without making destructive changes."""
    await init_db()
    async with get_db() as db:
        # Seed test devices
        await db.execute(
            "INSERT OR REPLACE INTO trusted_devices (device_id, user_id, display_name, public_key_jwk, key_fingerprint, status, last_ip) "
            "VALUES ('dev-sitanshu', 'sitanshu', 'Sitanshu Laptop', '{}', 'fp-sitanshu', 'approved', '127.0.0.1')"
        )
        await db.execute(
            "INSERT OR REPLACE INTO trusted_devices (device_id, user_id, display_name, public_key_jwk, key_fingerprint, status, last_ip) "
            "VALUES ('dev-rohit', 'rohit', 'Rohit Laptop', '{}', 'fp-rohit', 'approved', '10.10.145.22')"
        )
        await db.commit()

    # Run dry run
    res = await reset_demo_state(apply=False, mode="untrusted_only", target_user="rohit", as_json=True)
    assert res["applied"] is False
    assert any(d["user_id"] == "rohit" for d in res["removed_devices"])

    # Verify database still has Rohit
    async with get_db() as db:
        row = await (await db.execute("SELECT id FROM trusted_devices WHERE user_id = 'rohit'")).fetchone()
        assert row is not None
        await db.execute("DELETE FROM trusted_devices WHERE device_id IN ('dev-sitanshu', 'dev-rohit')")
        await db.commit()


@pytest.mark.asyncio
async def test_judge_reset_untrusted_only_preserves_team():
    """Verify untrusted-only mode removes Rohit while preserving team members and alerts."""
    await init_db()
    async with get_db() as db:
        # Seed team devices
        team = [
            ("dev-sitanshu", "sitanshu", "Sitanshu", "127.0.0.1"),
            ("dev-aryan", "aryan", "Aryan", "10.10.160.10"),
            ("dev-vicky", "vicky", "Vicky", "10.10.164.63"),
            ("dev-zara", "zara", "Zara", "10.10.163.208"),
            ("dev-rakshita", "rakshita", "Rakshita", "10.10.165.55"),
            ("dev-rohit", "rohit", "Rohit", "10.10.145.22"),
        ]
        for dev_id, user_id, name, ip in team:
            await db.execute(
                "INSERT OR REPLACE INTO trusted_devices (device_id, user_id, display_name, public_key_jwk, key_fingerprint, status, last_ip) "
                "VALUES (?, ?, ?, '{}', ?, 'approved', ?)",
                (dev_id, user_id, name, f"fp-{user_id}", ip),
            )

        # Seed sample alert in mailbox
        await db.execute(
            "INSERT INTO offline_security_alerts (alert_type, severity, subject, sender, recipients, body_text, composition_mode, evidence_pack_json) "
            "VALUES ('TEST_ALERT', 'LOW', 'Historical Alert 1', 'sys@internal', '[\"admin@internal\"]', 'text', 'FALLBACK', '{}')"
        )
        await db.commit()

    # Apply reset targeting Rohit with default preserve alerts
    res = await reset_demo_state(apply=True, mode="untrusted_only", target_user="rohit", wipe_mailbox=False, as_json=True)
    assert res["applied"] is True
    assert res["mailbox_status"] == "preserved"

    async with get_db() as db:
        # Rohit must be gone
        rohit_row = await (await db.execute("SELECT id FROM trusted_devices WHERE user_id = 'rohit'")).fetchone()
        assert rohit_row is None

        # All other team members must be preserved
        for _, u, _, _ in team:
            if u != "rohit":
                urow = await (await db.execute("SELECT id FROM trusted_devices WHERE user_id = ?", (u,))).fetchone()
                assert urow is not None, f"User {u} should be preserved across reset"

        # Historical alerts in mailbox must be preserved
        alerts_row = await (await db.execute("SELECT count(*) as n FROM offline_security_alerts")).fetchone()
        assert alerts_row["n"] >= 1

        # Clean up seeded team test devices
        for dev_id, _, _, _ in team:
            await db.execute("DELETE FROM trusted_devices WHERE device_id = ?", (dev_id,))
        await db.commit()


@pytest.mark.asyncio
async def test_judge_reset_wipe_mailbox_when_explicit():
    """Verify mailbox is only wiped when --wipe-mailbox is explicitly given."""
    await init_db()
    async with get_db() as db:
        # Seed an alert
        await db.execute(
            "INSERT INTO offline_security_alerts (alert_type, severity, subject, sender, recipients, body_text, composition_mode, evidence_pack_json) "
            "VALUES ('TEST_ALERT', 'LOW', 'Alert to be wiped', 'sys@internal', '[\"admin@internal\"]', 'text', 'FALLBACK', '{}')"
        )
        await db.commit()

    res = await reset_demo_state(apply=True, mode="untrusted_only", target_user="rohit", wipe_mailbox=True, as_json=True)
    assert res["mailbox_status"] == "wiped"

    async with get_db() as db:
        alerts_row = await (await db.execute("SELECT count(*) as n FROM offline_security_alerts")).fetchone()
        assert alerts_row["n"] == 0
