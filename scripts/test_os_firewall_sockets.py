"""Direct raw socket tester for OS Firewall Empirical Verification.
Bypasses application NetworkPolicy to directly test OS network stack behavior.
"""
import argparse
import json
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

def test_socket(target_host: str, target_port: int, timeout: float = 2.0) -> dict:
    start = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    ts = datetime.now(timezone.utc).isoformat()
    connected = False
    error_type = None
    error_msg = None
    error_code = None

    try:
        sock.connect((target_host, target_port))
        connected = True
    except Exception as e:
        connected = False
        error_type = type(e).__name__
        error_msg = str(e)
        if hasattr(e, "winerror"):
            error_code = e.winerror
        elif hasattr(e, "errno"):
            error_code = e.errno
    finally:
        try:
            sock.close()
        except Exception:
            pass

    elapsed = round((time.perf_counter() - start) * 1000, 2)
    return {
        "timestamp": ts,
        "executable": sys.executable,
        "target_host": target_host,
        "target_port": target_port,
        "timeout_seconds": timeout,
        "connected": connected,
        "blocked_by_os": not connected,
        "error_type": error_type,
        "error_message": error_msg,
        "error_code": error_code,
        "elapsed_ms": elapsed
    }

def main():
    parser = argparse.ArgumentParser(description="CogniShift Raw Socket OS Firewall Tester")
    parser.add_argument("--target-host", required=True, help="Target IP or hostname")
    parser.add_argument("--target-port", type=int, required=True, help="Target port")
    parser.add_argument("--timeout", type=float, default=2.0, help="Socket timeout in seconds")
    parser.add_argument("--output-json", required=True, help="Output path for JSON evidence")
    args = parser.parse_args()

    res = test_socket(args.target_host, args.target_port, args.timeout)
    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"[RAW SOCKET TEST] Target={args.target_host}:{args.target_port} -> Connected={res['connected']}, Error={res['error_type']}")

if __name__ == "__main__":
    main()
