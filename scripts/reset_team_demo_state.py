#!/usr/bin/env python3
"""Reset or check demo state for CogniShift multi-terminal LAN presentation.

Adheres strictly to CogniShift Core Trust Principles:
- ECDSA device possession is the cryptographic identity.
- Resetting for judges preserves approved devices for Aryan, Vicky, Zara, Rakshita, and Sitanshu.
- Only Rohit is reset to untrusted/unknown device to demonstrate the 403 UNKNOWN_DEVICE -> Administrator approval flow.
- Preserves security alerts in mailbox by default so evaluators can review historical telemetry.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db


async def reset_demo_state(
    apply: bool = False,
    mode: str = "untrusted_only",
    target_user: str = "rohit",
    wipe_mailbox: bool = False,
    as_json: bool = False,
) -> Dict[str, Any]:
    await init_db()
    
    result: Dict[str, Any] = {
        "applied": apply,
        "mode": mode,
        "target_user": target_user,
        "wipe_mailbox": wipe_mailbox,
        "devices_before": [],
        "devices_after": [],
        "removed_devices": [],
        "preserved_devices": [],
        "sessions_cleared": 0,
        "challenges_cleared": 0,
        "mailbox_status": "preserved",
        "alerts_purged": 0,
    }

    async with get_db() as db:
        devices = await (
            await db.execute(
                "SELECT device_id, user_id, display_name, status, last_ip, key_fingerprint FROM trusted_devices"
            )
        ).fetchall()
        result["devices_before"] = [dict(d) for d in devices]

        sessions = await (await db.execute("SELECT count(*) as n FROM active_device_sessions")).fetchone()
        challenges = await (await db.execute("SELECT count(*) as n FROM device_challenges")).fetchone()
        
        table_check = await (
            await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='offline_security_alerts'"
            )
        ).fetchone()
        alerts_count = 0
        if table_check:
            a_row = await (await db.execute("SELECT count(*) as n FROM offline_security_alerts")).fetchone()
            alerts_count = a_row["n"]

        if mode == "untrusted_only":
            to_remove = [d for d in devices if d["user_id"].lower() == target_user.lower()]
            to_keep = [d for d in devices if d["user_id"].lower() != target_user.lower()]
        else:  # all_devices
            to_remove = [d for d in devices if d["user_id"].lower() != "sitanshu"]
            to_keep = [d for d in devices if d["user_id"].lower() == "sitanshu"]

        result["removed_devices"] = [dict(d) for d in to_remove]
        result["preserved_devices"] = [dict(d) for d in to_keep]

        if not apply:
            result["sessions_cleared"] = sessions["n"]
            result["challenges_cleared"] = challenges["n"]
            result["alerts_count"] = alerts_count

            if not as_json:
                print("================================================================")
                print("       COGNISHIFT DEMO STATE INSPECTOR (DRY-RUN)")
                print("================================================================")
                print(f"Mode: {mode} (Target User: {target_user})")
                print(f"Current trusted devices ({len(devices)}):")
                for d in devices:
                    print(f"  - [{d['status'].upper():8}] user={d['user_id']:10} dev={d['device_id'][:12]}... ip={d['last_ip']}")
                print(f"Active sessions: {sessions['n']} | Pending challenges: {challenges['n']}")
                print(f"Security alerts in mailbox: {alerts_count} (Preserved by default)")
                print("\n[DRY RUN SUMMARY] If --apply is passed:")
                print(f"  * Devices to unapprove/remove: {[d['user_id'] for d in to_remove]}")
                print(f"  * Devices to preserve: {[d['user_id'] for d in to_keep]}")
                print(f"  * Mailbox: {'WIPE' if wipe_mailbox else 'PRESERVE (no alerts deleted)'}")
                print("\nRun with --apply to execute this reset.")
            return result

        # APPLY CHANGES
        if mode == "untrusted_only":
            await db.execute("DELETE FROM trusted_devices WHERE LOWER(user_id) = LOWER(?)", (target_user,))
            sess_del = await db.execute("DELETE FROM active_device_sessions WHERE LOWER(user_id) = LOWER(?)", (target_user,))
            chal_del = await db.execute("DELETE FROM device_challenges WHERE LOWER(user_id) = LOWER(?)", (target_user,))
            result["sessions_cleared"] = sess_del.rowcount
            result["challenges_cleared"] = chal_del.rowcount
        else:
            await db.execute("DELETE FROM trusted_devices WHERE LOWER(user_id) != 'sitanshu'")
            sess_del = await db.execute("DELETE FROM active_device_sessions WHERE LOWER(user_id) != 'sitanshu'")
            chal_del = await db.execute("DELETE FROM device_challenges WHERE LOWER(user_id) != 'sitanshu'")
            result["sessions_cleared"] = sess_del.rowcount
            result["challenges_cleared"] = chal_del.rowcount

        if wipe_mailbox:
            if table_check:
                await db.execute("DELETE FROM notification_citations")
                del_a = await db.execute("DELETE FROM offline_security_alerts")
                result["alerts_purged"] = del_a.rowcount
            mailbox_dir = Path("data/alerts/mailbox")
            if mailbox_dir.exists():
                for f in mailbox_dir.glob("*.eml"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
            result["mailbox_status"] = "wiped"
        else:
            result["mailbox_status"] = "preserved"

        await db.commit()

        devices_after = await (
            await db.execute(
                "SELECT device_id, user_id, display_name, status, last_ip FROM trusted_devices"
            )
        ).fetchall()
        result["devices_after"] = [dict(d) for d in devices_after]

        if not as_json:
            print("================================================================")
            print("       COGNISHIFT DEMO STATE RESET - APPLIED SUCCESSFULLY")
            print("================================================================")
            print(f"Mode: {mode}")
            print(f"Preserved trusted devices ({len(devices_after)}):")
            for d in devices_after:
                print(f"  - [{d['status'].upper():8}] user={d['user_id']:10} dev={d['device_id'][:12]}... ip={d['last_ip']}")
            print(f"Sessions cleared: {result['sessions_cleared']} | Challenges cleared: {result['challenges_cleared']}")
            print(f"Security mailbox: {result['mailbox_status'].upper()} ({alerts_count} historical alerts kept)")
            if mode == "untrusted_only":
                print(f"\n[READY FOR JUDGE DEMO] User '{target_user}' is reset to UNTRUSTED.")
                print(f"When '{target_user}' attempts to connect, the system will block with 403 UNKNOWN_DEVICE")
                print("and trigger an executive security alert to the Administrator.")
            else:
                print("\n[READY FOR JUDGE DEMO] All remote devices reset. Only 'sitanshu' is preserved.")

        return result


def main():
    parser = argparse.ArgumentParser(description="Reset CogniShift demo state for finals.")
    parser.add_argument("--apply", action="store_true", help="Apply state reset (destructive writes)")
    parser.add_argument("--untrusted-only", action="store_true", default=True, help="Reset only untrusted demo user (default: True)")
    parser.add_argument("--all-devices", action="store_true", help="Reset all client devices, keeping only host admin 'sitanshu'")
    parser.add_argument("--target-user", type=str, default="rohit", help="Target untrusted demo user (default: rohit)")
    parser.add_argument("--wipe-mailbox", action="store_true", help="Explicitly wipe security alerts mailbox (default: False)")
    parser.add_argument("--preserve-alerts", action="store_true", default=True, help="Preserve security mailbox (default: True)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()
    mode = "all_devices" if args.all_devices else "untrusted_only"
    wipe = args.wipe_mailbox

    res = asyncio.run(reset_demo_state(
        apply=args.apply,
        mode=mode,
        target_user=args.target_user,
        wipe_mailbox=wipe,
        as_json=args.json
    ))

    if args.json:
        print(json.dumps(res, default=str))


if __name__ == "__main__":
    main()
