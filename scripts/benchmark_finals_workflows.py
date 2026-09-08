#!/usr/bin/env python3
"""
CogniShift SIH Finals Workflow Benchmark Suite.
Empirical latency, concurrency, and SLA verification across 10 critical workflows:
1. Device Verification
2. Authorization Creation
3. Supervisor Approval #1
4. Supervisor Approval #2 (Immediate Ack SLA < 1000ms)
5. Atomic Permit Execution
6. Consumed Rejection Fail-Closed
7. Mailbox List Retrieval
8. Mailbox Detail Retrieval
9. Notification Evidence Composition
10. Local Loopback SMTP Delivery
11. Five-Client Concurrency Load Test (Aryan, Vicky, Zara, Rakshita, Sitanshu)
"""
import argparse
import asyncio
import base64
import json
import math
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# Set UTF-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure cognishift is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import ASGITransport, AsyncClient

from cognishift.app.core.auth import User, create_ephemeral_demo_session
from cognishift.app.core.device_security import key_fingerprint
from cognishift.app.db.database import get_db, init_db
from cognishift.app.main import app
from cognishift.core.authorizations import process_pending_post_approval_jobs
from cognishift.core.notifications import (
    CitationClass,
    NotificationCitation,
    NotificationEvidencePack,
    NotificationType,
    Severity,
    compose_notification,
    send_internal_email,
    start_local_smtp_server,
    stop_local_smtp_server,
    check_smtp_health,
)


def enc(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def generate_identity(device_id: str, display_name: str = "Benchmark Terminal"):
    key = ec.generate_private_key(ec.SECP256R1())
    numbers = key.public_key().public_numbers()
    jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": enc(numbers.x.to_bytes(32, "big")),
        "y": enc(numbers.y.to_bytes(32, "big")),
    }
    return key, {"device_id": device_id, "display_name": display_name, "public_key_jwk": jwk}


async def solve_challenge(client: AsyncClient, auth_header: dict, key, payload: dict):
    res = await client.post("/api/v1/auth/device/challenge", json=payload, headers=auth_header)
    if res.status_code != 200:
        return res, None

    body = res.json()
    raw_chal = base64.urlsafe_b64decode(body["challenge"] + "=" * (-len(body["challenge"]) % 4))
    sig = key.sign(raw_chal, ec.ECDSA(hashes.SHA256()))
    verify_res = await client.post(
        "/api/v1/auth/device/verify",
        json={
            "device_id": payload["device_id"],
            "challenge_id": body["challenge_id"],
            "signature": enc(sig),
        },
        headers=auth_header,
    )
    if verify_res.status_code != 200:
        return verify_res, None
    return verify_res, verify_res.json()["device_session"]


def calc_stats(latencies_ms: List[float]) -> Dict[str, float]:
    """Calculate min, p50, p95, max for latency samples."""
    if not latencies_ms:
        return {"min": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    sorted_l = sorted(latencies_ms)
    n = len(sorted_l)
    p50_idx = int(0.50 * n)
    p95_idx = min(n - 1, math.ceil(0.95 * n) - 1)
    return {
        "min": round(sorted_l[0], 2),
        "p50": round(sorted_l[p50_idx], 2),
        "p95": round(sorted_l[p95_idx], 2),
        "max": round(sorted_l[-1], 2),
    }


async def run_benchmark(iterations: int = 20) -> Dict[str, Any]:
    print("=" * 105)
    print("                      === COGNISHIFT FINALS WORKFLOW BENCHMARK SUITE ===")
    print(f"       Target Iterations: {iterations} per operation | Authoritative Local Benchmark (Zero Cloud)")
    print("=" * 105)

    # 1. Initialize DB & Workspace
    await init_db()
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name, description) VALUES (1, 'Plant Unit 1', 'SIH Finals')")
        await db.commit()

    # 2. Start loopback SMTP server
    smtp_server = None
    try:
        smtp_server = await start_local_smtp_server(host="127.0.0.1", port=1025)
    except Exception as e:
        print(f"  [Notice] Local SMTP server: {e}")

    # 3. Setup personas
    personas = {
        "aryan": User(user_id="aryan", role="operator", allowed_workspace_ids=[1]),
        "vicky": User(user_id="vicky", role="supervisor", allowed_workspace_ids=[1]),
        "zara": User(user_id="zara", role="supervisor", allowed_workspace_ids=[1]),
        "rakshita": User(user_id="rakshita", role="supervisor", allowed_workspace_ids=[1]),
        "sitanshu": User(user_id="sitanshu", role="administrator", allowed_workspace_ids=[1]),
    }
    tokens = {}
    raw_tokens = {}
    for name, user in personas.items():
        tok, _ = create_ephemeral_demo_session(user)
        tokens[name] = {"Authorization": f"Bearer {tok}"}
        raw_tokens[name] = tok

    # Tracking metrics
    bench_results: Dict[str, Any] = {}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        # Pre-verify devices for each persona to obtain genuine sovereign device sessions
        for name in personas:
            dev_id = f"term-{name}-bench"
            key, payload = generate_identity(dev_id, f"{name.capitalize()} Terminal")
            fp = key_fingerprint(payload["public_key_jwk"])
            async with get_db() as db:
                await db.execute(
                    """INSERT OR REPLACE INTO trusted_devices 
                       (device_id, user_id, display_name, public_key_jwk, key_fingerprint, status)
                       VALUES (?, ?, ?, ?, ?, 'approved')""",
                    (dev_id, name, f"{name.capitalize()} Terminal", json.dumps(payload["public_key_jwk"]), fp),
                )
                await db.commit()
            _, dev_sess = await solve_challenge(client, {"Authorization": f"Bearer {raw_tokens[name]}"}, key, payload)
            tokens[name] = {
                "Authorization": f"Bearer {raw_tokens[name]}",
                "X-Device-Session": dev_sess or "",
            }

        # -------------------------------------------------------------
        # 1. Device Verification (Challenge & Cryptographic Signature)
        # -------------------------------------------------------------
        print("\n[1/11] Benchmarking Device Identity & Signature Verification...")
        lat_device = []
        err_device = 0
        for i in range(iterations):
            try:
                dev_id = f"bench-dev-test-{i}-{int(time.time())}"
                key, payload = generate_identity(dev_id)
                fp = key_fingerprint(payload["public_key_jwk"])
                async with get_db() as db:
                    await db.execute(
                        """INSERT OR REPLACE INTO trusted_devices 
                           (device_id, user_id, display_name, public_key_jwk, key_fingerprint, status)
                           VALUES (?, 'aryan', 'Bench Terminal', ?, ?, 'approved')""",
                        (dev_id, json.dumps(payload["public_key_jwk"]), fp),
                    )
                    await db.commit()

                t0 = time.perf_counter()
                res, session = await solve_challenge(client, tokens["aryan"], key, payload)
                lat = (time.perf_counter() - t0) * 1000
                if res.status_code == 200 and session:
                    lat_device.append(lat)
                else:
                    err_device += 1
            except Exception as e:
                err_device += 1

        bench_results["1. Device Verification"] = {
            "stats": calc_stats(lat_device),
            "errors": err_device,
            "sla": 250.0,
        }

        # -------------------------------------------------------------
        # 2. Authorization Creation (Operator Permit Request)
        # -------------------------------------------------------------
        print("[2/11] Benchmarking Temporary Authorization Creation...")
        lat_create = []
        err_create = 0
        permit_ids = []
        permit_codes = []
        for i in range(iterations):
            try:
                t0 = time.perf_counter()
                res = await client.post(
                    "/api/v1/authorizations",
                    json={
                        "workspace_id": 1,
                        "user_id": "aryan",
                        "action": "operate_pump",
                        "resource": f"P-{101 + i % 5}A",
                        "reason": f"SOP-PUMP-TRANSFER benchmark iteration {i}",
                        "max_uses": 1,
                        "valid_minutes": 60,
                    },
                    headers=tokens["aryan"],
                )
                lat = (time.perf_counter() - t0) * 1000
                if res.status_code == 201:
                    lat_create.append(lat)
                    d = res.json()
                    permit_ids.append(d["id"])
                    permit_codes.append(d["permit_code"])
                else:
                    print(f"  [DEBUG 2] status={res.status_code} body={res.text}")
                    err_create += 1
            except Exception as e:
                print(f"  [DEBUG 2 EX] {e}")
                err_create += 1

        bench_results["2. Authorization Creation"] = {
            "stats": calc_stats(lat_create),
            "errors": err_create,
            "sla": 250.0,
        }

        # -------------------------------------------------------------
        # 3. Supervisor Approval #1 (Zara Stage 1/2)
        # -------------------------------------------------------------
        print("[3/11] Benchmarking Supervisor Approval #1 (Zara Stage 1/2)...")
        lat_appr1 = []
        err_appr1 = 0
        for pid in permit_ids:
            try:
                t0 = time.perf_counter()
                res = await client.post(
                    f"/api/v1/authorizations/{pid}/approve",
                    json={"comments": "Stage 1 hydraulic pressure verified"},
                    headers=tokens["zara"],
                )
                lat = (time.perf_counter() - t0) * 1000
                if res.status_code == 200:
                    lat_appr1.append(lat)
                else:
                    err_appr1 += 1
            except Exception:
                err_appr1 += 1

        bench_results["3. Supervisor Approval #1"] = {
            "stats": calc_stats(lat_appr1),
            "errors": err_appr1,
            "sla": 250.0,
        }

        # -------------------------------------------------------------
        # 4. Supervisor Approval #2 (Rakshita Stage 2/2 -> Immediate Ack SLA)
        # -------------------------------------------------------------
        print("[4/11] Benchmarking Supervisor Approval #2 (Rakshita Stage 2/2 Immediate Ack)...")
        lat_appr2 = []
        err_appr2 = 0
        for pid in permit_ids:
            try:
                t0 = time.perf_counter()
                res = await client.post(
                    f"/api/v1/authorizations/{pid}/approve",
                    json={"comments": "Stage 2 secondary containment confirmed"},
                    headers=tokens["rakshita"],
                )
                lat = (time.perf_counter() - t0) * 1000
                if res.status_code == 200 and res.json()["status"] == "ACTIVE":
                    lat_appr2.append(lat)
                else:
                    err_appr2 += 1
            except Exception:
                err_appr2 += 1

        bench_results["4. Supervisor Approval #2"] = {
            "stats": calc_stats(lat_appr2),
            "errors": err_appr2,
            "sla": 1000.0,
        }

        # -------------------------------------------------------------
        # 5. Atomic Permit Execution (Aryan consumes 1-use permit)
        # -------------------------------------------------------------
        print("[5/11] Benchmarking Atomic Permit Execution (CAS Consumption)...")
        lat_exec = []
        err_exec = 0
        for i, pcode in enumerate(permit_codes):
            try:
                t0 = time.perf_counter()
                res = await client.post(
                    "/api/v1/authorizations/execute",
                    json={
                        "permit_code": pcode,
                        "action": "operate_pump",
                        "resource": f"P-{101 + i % 5}A",
                        "parameters": {"mode": "START", "flow_rate": 150.0},
                    },
                    headers=tokens["aryan"],
                )
                lat = (time.perf_counter() - t0) * 1000
                if res.status_code == 200 and res.json()["status"] == "CONSUMED":
                    lat_exec.append(lat)
                else:
                    err_exec += 1
            except Exception:
                err_exec += 1

        bench_results["5. Atomic Permit Execution"] = {
            "stats": calc_stats(lat_exec),
            "errors": err_exec,
            "sla": 250.0,
        }

        # -------------------------------------------------------------
        # 6. Consumed Rejection Check (Fail-Closed second call)
        # -------------------------------------------------------------
        print("[6/11] Benchmarking Consumed Rejection (Fail-Closed Check)...")
        lat_reject = []
        err_reject = 0
        for i, pcode in enumerate(permit_codes):
            try:
                t0 = time.perf_counter()
                res = await client.post(
                    "/api/v1/authorizations/execute",
                    json={
                        "permit_code": pcode,
                        "action": "operate_pump",
                        "resource": f"P-{101 + i % 5}A",
                    },
                    headers=tokens["aryan"],
                )
                lat = (time.perf_counter() - t0) * 1000
                if res.status_code == 403 and "AUTHORIZATION_CONSUMED" in res.json().get("detail", ""):
                    lat_reject.append(lat)
                else:
                    err_reject += 1
            except Exception:
                err_reject += 1

        bench_results["6. Consumed Rejection Check"] = {
            "stats": calc_stats(lat_reject),
            "errors": err_reject,
            "sla": 250.0,
        }

        # Background drain
        await process_pending_post_approval_jobs()

        # -------------------------------------------------------------
        # 7. Mailbox List Retrieval (Role-Scoped Index Query)
        # -------------------------------------------------------------
        print("[7/11] Benchmarking Role-Scoped Mailbox List Retrieval...")
        lat_mblist = []
        err_mblist = 0
        for _ in range(iterations):
            try:
                t0 = time.perf_counter()
                res = await client.get("/api/v1/mail?limit=50", headers=tokens["aryan"])
                lat = (time.perf_counter() - t0) * 1000
                if res.status_code == 200:
                    lat_mblist.append(lat)
                else:
                    err_mblist += 1
            except Exception:
                err_mblist += 1

        bench_results["7. Mailbox List Retrieval"] = {
            "stats": calc_stats(lat_mblist),
            "errors": err_mblist,
            "sla": 150.0,
        }

        # -------------------------------------------------------------
        # 8. Mailbox Detail Retrieval (Full HTML/Text/Citations)
        # -------------------------------------------------------------
        print("[8/11] Benchmarking Mailbox Detail Retrieval...")
        lat_mbdetail = []
        err_mbdetail = 0
        list_res = await client.get("/api/v1/mail?limit=10", headers=tokens["aryan"])
        sample_messages = list_res.json().get("messages", [])
        if not sample_messages:
            # Generate test dispatch so mailbox contains at least one record
            await client.post("/api/v1/mail/dispatch-test", headers=tokens["sitanshu"])
            list_res = await client.get("/api/v1/mail?limit=10", headers=tokens["aryan"])
            sample_messages = list_res.json().get("messages", [])
        sample_id = sample_messages[0]["id"] if sample_messages else 1

        for _ in range(iterations):
            try:
                t0 = time.perf_counter()
                res = await client.get(f"/api/v1/mail/{sample_id}", headers=tokens["aryan"])
                lat = (time.perf_counter() - t0) * 1000
                if res.status_code == 200:
                    lat_mbdetail.append(lat)
                else:
                    err_mbdetail += 1
            except Exception:
                err_mbdetail += 1

        bench_results["8. Mailbox Detail Retrieval"] = {
            "stats": calc_stats(lat_mbdetail),
            "errors": err_mbdetail,
            "sla": 150.0,
        }

        # -------------------------------------------------------------
        # 9. Notification Evidence Composition
        # -------------------------------------------------------------
        print("[9/11] Benchmarking Notification Evidence Composition...")
        lat_compose = []
        err_compose = 0
        for i in range(iterations):
            try:
                ev = NotificationEvidencePack(
                    event_type=NotificationType.ACCESS_AUTHORIZATION,
                    severity=Severity.HIGH,
                    actor_id="rakshita",
                    target_user="aryan",
                    workspace_id=1,
                    tool_name="operate_pump [P-101A]",
                    permit_code=f"BENCH-PERMIT-{i:04d}",
                    uses_remaining=1,
                    correlation_id=f"corr-bench-{i}",
                    summary="Benchmarking local notification composition engine",
                    citations=[
                        NotificationCitation(
                            citation_index=1,
                            citation_type=CitationClass.AUTHORIZATION,
                            display_label="Permit BENCH",
                            source_id=f"BENCH-{i}",
                            validated=True,
                        )
                    ],
                )
                t0 = time.perf_counter()
                comp = await compose_notification(
                    evidence=ev,
                    sender="governance-bot@secure.internal",
                    recipients=["aryan@secure.internal", "zara@secure.internal"],
                )
                lat = (time.perf_counter() - t0) * 1000
                if comp and comp.subject and comp.body_html:
                    lat_compose.append(lat)
                else:
                    err_compose += 1
            except Exception as e:
                err_compose += 1

        bench_results["9. Notification Composition"] = {
            "stats": calc_stats(lat_compose),
            "errors": err_compose,
            "sla": 250.0,
        }

        # -------------------------------------------------------------
        # 10. SMTP Loopback Delivery (RFC 5321 Handshake)
        # -------------------------------------------------------------
        print("[10/11] Benchmarking RFC 5321 Local Loopback SMTP Delivery...")
        lat_smtp = []
        err_smtp = 0
        for i in range(iterations):
            try:
                t0 = time.perf_counter()
                delivered = await send_internal_email(
                    sender="governance-bot@secure.internal",
                    recipients=["aryan@secure.internal"],
                    subject=f"[BENCHMARK] Test Loopback Delivery #{i}",
                    body_text="Test RFC 5321 loopback transmission",
                    body_html="<p>Test RFC 5321 loopback transmission</p>",
                )
                lat = (time.perf_counter() - t0) * 1000
                if delivered:
                    lat_smtp.append(lat)
                else:
                    err_smtp += 1
            except Exception:
                err_smtp += 1

        bench_results["10. SMTP Loopback Delivery"] = {
            "stats": calc_stats(lat_smtp),
            "errors": err_smtp,
            "sla": 200.0,
        }

        # -------------------------------------------------------------
        # 11. Five-Client Concurrency Load Test (5 Simultaneous Personas)
        # -------------------------------------------------------------
        print("[11/11] Benchmarking 5-Client Concurrency Load Test (50 Operations)...")
        lat_concurrent = []
        err_concurrent = 0

        async def worker_task(user_name: str, task_type: str, iter_idx: int) -> float:
            t0 = time.perf_counter()
            token_hdr = tokens[user_name]
            if task_type == "request":
                r = await client.post(
                    "/api/v1/authorizations",
                    json={"workspace_id": 1, "user_id": user_name, "action": "operate_pump", "resource": "P-101A", "reason": "load"},
                    headers=token_hdr,
                )
                if r.status_code != 201:
                    raise RuntimeError(f"Request failed: {r.status_code}")
            elif task_type == "mailbox":
                r = await client.get("/api/v1/mail?limit=20", headers=token_hdr)
                if r.status_code != 200:
                    raise RuntimeError(f"Mailbox failed: {r.status_code}")
            elif task_type == "audit":
                r = await client.get("/api/v1/security/status?workspace_id=1", headers=token_hdr)
                if r.status_code != 200:
                    raise RuntimeError(f"Status failed: {r.status_code} {r.text}")
            return (time.perf_counter() - t0) * 1000

        # Run 10 waves of 5 concurrent requests (50 total operations)
        for wave in range(10):
            tasks = [
                worker_task("aryan", "request", wave),
                worker_task("vicky", "mailbox", wave),
                worker_task("zara", "mailbox", wave),
                worker_task("rakshita", "mailbox", wave),
                worker_task("sitanshu", "audit", wave),
            ]
            wave_res = await asyncio.gather(*tasks, return_exceptions=True)
            for res in wave_res:
                if isinstance(res, Exception):
                    err_concurrent += 1
                else:
                    lat_concurrent.append(res)

        bench_results["11. 5-Client Concurrent Load"] = {
            "stats": calc_stats(lat_concurrent),
            "errors": err_concurrent,
            "sla": 1000.0,
        }

    # 4. Format and print authoritative report
    all_passed = True
    print("\n" + "=" * 105)
    print("                              === COGNISHIFT FINALS PERFORMANCE REPORT ===")
    print("=" * 105)
    print(f"{'Workflow Operation':<32} {'Count':>6} {'Min(ms)':>9} {'p50(ms)':>9} {'p95(ms)':>9} {'Max(ms)':>9} {'Errors':>7} {'SLA(ms)':>9} {'Verdict':>9}")
    print("-" * 105)

    for op_name, data in bench_results.items():
        st = data["stats"]
        errs = data["errors"]
        sla = data["sla"]
        # Pass criterion: p95 <= sla and errors == 0
        passed = (st["p95"] <= sla) and (errs == 0)
        verdict = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False

        print(
            f"{op_name:<32} {iterations if 'Concurrent' not in op_name else len(lat_concurrent):>6} "
            f"{st['min']:>9.2f} {st['p50']:>9.2f} {st['p95']:>9.2f} {st['max']:>9.2f} "
            f"{errs:>7} {sla:>9.1f} {verdict:>9}"
        )

    print("=" * 105)
    overall = "PASS (ALL CRITICAL PATH SLAS VERIFIED)" if all_passed else "FAIL (ONE OR MORE SLAS BREACHED)"
    print(f"OVERALL BENCHMARK VERDICT: {overall}")
    print("=" * 105 + "\n")

    if smtp_server:
        try:
            await stop_local_smtp_server()
        except Exception:
            pass

    return {
        "verdict": overall,
        "all_passed": all_passed,
        "results": bench_results,
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CogniShift Finals Workflow Benchmark Suite")
    parser.add_argument("--iterations", type=int, default=20, help="Iterations per operation (default: 20)")
    parser.add_argument("--json-out", type=str, default=None, help="Optional path to output JSON results")
    args = parser.parse_args()

    result = asyncio.run(run_benchmark(iterations=args.iterations))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"Results exported to {args.json_out}")

    sys.exit(0 if result["all_passed"] else 1)
