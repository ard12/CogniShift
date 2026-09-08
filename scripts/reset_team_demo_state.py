#!/usr/bin/env python3
"""Reset or check demo state for CogniShift multi-terminal LAN presentation."""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cognishift.app.db.database import get_db, init_db


async def reset_demo_state(apply: bool = False):
    await init_db()
    print("=== COGNISHIFT DEMO STATE INSPECTOR ===")
    async with get_db() as db:
        devices = await (await db.execute("SELECT device_id, user_id, display_name, status, last_ip FROM trusted_devices")).fetchall()
        print(f"Current trusted_devices count: {len(devices)}")
        for d in devices:
            print(f"  - [{d['status'].upper()}] device={d['device_id']} user={d['user_id']} ip={d['last_ip']}")

        sessions = await (await db.execute("SELECT count(*) as n FROM active_device_sessions")).fetchone()
        challenges = await (await db.execute("SELECT count(*) as n FROM device_challenges")).fetchone()
        print(f"Active device sessions: {sessions['n']}")
        print(f"Device challenges: {challenges['n']}")

        if not apply:
            print("\n[DRY RUN] No changes applied. Run with --apply to reset demo state.")
            return

        print("\n[APPLYING RESET] Purging sessions, challenges, and unapproving Rohit's device...")
        await db.execute("DELETE FROM active_device_sessions")
        await db.execute("DELETE FROM device_challenges")
        # Ensure Rohit is pending or absent so Rohit cannot bypass approval
        await db.execute("DELETE FROM trusted_devices WHERE user_id = 'rohit'")
        await db.commit()
        print("[SUCCESS] Demo state cleanly reset. Rohit is marked UNKNOWN/PENDING for live challenge.")


def main():
    parser = argparse.ArgumentParser(description="Reset CogniShift demo state.")
    parser.add_argument("--apply", action="store_true", help="Apply state reset")
    args = parser.parse_args()
    asyncio.run(reset_demo_state(apply=args.apply))


if __name__ == "__main__":
    main()
