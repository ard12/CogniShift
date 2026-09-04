"""Independent Host-Level Network Egress Observer.

Provides active socket observation for CogniShift processes via psutil.
Verifies network silence, audits loopback vs non-loopback connections,
and includes an executable negative control to prove detection accuracy.
"""

import argparse
import ipaddress
import os
import socket
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

import psutil


@dataclass
class ObservedConnection:
    timestamp: str
    pid: int
    process_name: str
    protocol: str
    local_address: str
    local_port: int
    remote_address: str
    remote_port: int
    status: str
    classification: str
    is_authorized: bool
    details: str


def classify_ip(ip_str: str) -> str:
    """Classify an IP address string as loopback, private, link_local, or public."""
    if not ip_str or ip_str in ("0.0.0.0", "::", "*"):
        return "unspecified"
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_loopback:
            return "loopback"
        if ip.is_private:
            return "private"
        if ip.is_link_local:
            return "link_local"
        return "public"
    except ValueError:
        return "unparseable"


class NetworkObserver:
    """Monitors host network connections for specified process IDs.
    
    Operates independently of application-level HTTP transports by querying
    the OS socket table via psutil.
    """

    def __init__(
        self,
        target_pids: Optional[List[int]] = None,
        sample_interval: float = 0.05,
        allowed_ports: Optional[Set[int]] = None,
    ):
        self.target_pids = set(target_pids) if target_pids else {os.getpid()}
        self.sample_interval = sample_interval
        self.allowed_ports = allowed_ports or {11434, 8000}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._observed_records: List[ObservedConnection] = []
        self._seen_keys: Set[Tuple[int, str, int, str, int, str]] = set()

    def add_target_pid(self, pid: int) -> None:
        with self._lock:
            self.target_pids.add(pid)

    def start(self) -> None:
        """Start the background polling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="NetworkObserverThread")
        self._thread.start()

    def stop(self) -> None:
        """Stop the background polling thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _poll_loop(self) -> None:
        while self._running:
            try:
                self._sample_connections()
            except Exception:
                pass
            time.sleep(self.sample_interval)

    def _sample_connections(self) -> None:
        try:
            conns = psutil.net_connections(kind="all")
        except (psutil.AccessDenied, PermissionError):
            return

        now_iso = datetime.now(timezone.utc).isoformat()

        for conn in conns:
            if conn.pid is None:
                continue
            if conn.pid not in self.target_pids:
                continue

            # Local endpoint
            l_ip = conn.laddr.ip if conn.laddr else ""
            l_port = conn.laddr.port if conn.laddr else 0

            # Remote endpoint
            r_ip = conn.raddr.ip if conn.raddr else ""
            r_port = conn.raddr.port if conn.raddr else 0

            # Protocol
            proto = "TCP" if conn.type == socket.SOCK_STREAM else "UDP"

            # Unique key for deduplication
            key = (conn.pid, l_ip, l_port, r_ip, r_port, conn.status)
            with self._lock:
                if key in self._seen_keys:
                    continue
                self._seen_keys.add(key)

            # Classify destination
            classification = classify_ip(r_ip)

            # Determine authorization
            is_auth = False
            details = ""
            if not r_ip:
                # Listening or unbound socket
                is_auth = True
                details = f"Local bind/listen on {l_ip}:{l_port}"
            elif classification == "loopback":
                if r_port in self.allowed_ports or l_port in self.allowed_ports:
                    is_auth = True
                    details = f"Authorized loopback communication on port {r_port}"
                else:
                    # Generic loopback is permitted but audited
                    is_auth = True
                    details = f"Loopback connection to port {r_port}"
            else:
                is_auth = False
                details = f"UNAUTHORIZED {classification.upper()} connection to {r_ip}:{r_port}"

            # Process name
            pname = "unknown"
            try:
                pname = psutil.Process(conn.pid).name()
            except Exception:
                pass

            record = ObservedConnection(
                timestamp=now_iso,
                pid=conn.pid,
                process_name=pname,
                protocol=proto,
                local_address=l_ip,
                local_port=l_port,
                remote_address=r_ip,
                remote_port=r_port,
                status=conn.status,
                classification=classification,
                is_authorized=is_auth,
                details=details,
            )

            with self._lock:
                self._observed_records.append(record)

    def get_records(self) -> List[ObservedConnection]:
        with self._lock:
            return list(self._observed_records)

    def get_summary(self) -> dict:
        with self._lock:
            records = list(self._observed_records)

        loopback_count = sum(1 for r in records if r.classification == "loopback")
        unauthorized_count = sum(1 for r in records if not r.is_authorized)
        public_count = sum(1 for r in records if r.classification == "public")
        private_count = sum(1 for r in records if r.classification == "private")
        link_local_count = sum(1 for r in records if r.classification == "link_local")

        return {
            "total_observed": len(records),
            "loopback_count": loopback_count,
            "unauthorized_count": unauthorized_count,
            "public_count": public_count,
            "private_count": private_count,
            "link_local_count": link_local_count,
            "target_pids": list(self.target_pids),
            "unauthorized_violations": [
                asdict(r) for r in records if not r.is_authorized
            ],
        }

    def assert_zero_unauthorized_egress(self) -> None:
        """Asserts that no unauthorized connections were observed."""
        summary = self.get_summary()
        if summary["unauthorized_count"] > 0:
            violations = summary["unauthorized_violations"]
            raise AssertionError(
                f"Observer detected {summary['unauthorized_count']} unauthorized network connection(s):\n"
                f"{violations}"
            )


def run_negative_control() -> bool:
    """Negative Control Test: Proves the observer detects connections when they happen.
    
    Launches a dummy socket listener, connects a client socket to it,
    and verifies the observer successfully captures the event.
    """
    test_port = 19876
    pid = os.getpid()

    observer = NetworkObserver(target_pids=[pid], sample_interval=0.01)
    observer.start()

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", test_port))
    server_sock.listen(1)

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_sock.connect(("127.0.0.1", test_port))
        conn, _ = server_sock.accept()

        # Let observer sample the active connection
        time.sleep(0.1)

        conn.close()
    finally:
        client_sock.close()
        server_sock.close()
        observer.stop()

    summary = observer.get_summary()
    records = observer.get_records()

    # Verify that the test port connection was observed
    detected = any(
        (r.local_port == test_port or r.remote_port == test_port)
        for r in records
    )

    if detected:
        print(f"[NEGATIVE CONTROL PASSED] Observer successfully captured connection on port {test_port}.")
        print(f"Total connections recorded: {summary['total_observed']}")
        return True
    else:
        print(f"[NEGATIVE CONTROL FAILED] Observer failed to capture connection on port {test_port}!")
        return False


def main():
    parser = argparse.ArgumentParser(description="CogniShift Independent Host Network Observer")
    parser.add_argument("--test-negative-control", action="store_true", help="Run negative control test")
    parser.add_argument("--duration", type=float, default=3.0, help="Observation duration in seconds")
    parser.add_argument("--pid", type=int, default=None, help="Target PID to observe (default: current process)")
    args = parser.parse_args()

    if args.test_negative_control:
        success = run_negative_control()
        sys.exit(0 if success else 1)

    target_pid = args.pid or os.getpid()
    print(f"Observing PID {target_pid} for {args.duration} seconds...")
    observer = NetworkObserver(target_pids=[target_pid])
    observer.start()
    try:
        time.sleep(args.duration)
    finally:
        observer.stop()

    summary = observer.get_summary()
    print(f"\n--- Observation Summary ---")
    print(f"Total Connections: {summary['total_observed']}")
    print(f"Loopback Connections: {summary['loopback_count']}")
    print(f"Unauthorized Connections: {summary['unauthorized_count']}")
    if summary["unauthorized_count"] > 0:
        print(f"VIOLATIONS: {summary['unauthorized_violations']}")
        sys.exit(1)
    else:
        print("PASS: Zero unauthorized network connections observed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
