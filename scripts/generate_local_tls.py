#!/usr/bin/env python3
"""CLI utility to generate or regenerate local TLS certificates for LAN deployment."""
import argparse
import ssl
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import socket
from cognishift.app.core.tls import ensure_local_tls_certificates, get_default_cert_dir, get_cert_sans


def validate_tls_pair(cert_path: Path, key_path: Path, attempts: int = 5) -> None:
    """Confirm the files are readable by the same OpenSSL API Uvicorn uses.

    OneDrive-backed workspaces can briefly expose a just-replaced PEM file as
    unavailable to a second process. A bounded retry prevents a transient sync
    window from aborting the LAN launcher.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
            return
        except (OSError, ssl.SSLError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(0.4)
    raise RuntimeError(f"TLS certificate/key validation failed after {attempts} attempts: {last_error}")


def detect_host_ips() -> list[str]:
    """Detect non-loopback, non-link-local IPv4 addresses on host network adapters."""
    detected = ["127.0.0.1"]
    try:
        import psutil
        for iface_name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if (str(addr.family).endswith("AF_INET") or addr.family == 2):
                    ip = addr.address
                    if not ip.startswith("127.") and not ip.startswith("169.254."):
                        detected.append(ip)
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                detected.append(ip)
    except Exception:
        pass

    return list(dict.fromkeys(detected))


def main():
    parser = argparse.ArgumentParser(description="Generate local TLS CA and Server certificates.")
    parser.add_argument("--ip", action="append", default=None, help="Server IP address for SAN")
    parser.add_argument("--hostname", action="append", default=["localhost"], help="Server hostname for SAN")
    parser.add_argument("--outdir", default=None, help="Output directory for certificates")
    parser.add_argument("--force", action="store_true", help="Force regenerate certificates")

    args = parser.parse_args()
    outdir = Path(args.outdir) if args.outdir else get_default_cert_dir()

    ips = list(set(args.ip)) if args.ip else detect_host_ips()
    hostnames = list(set(args.hostname))

    if args.force:
        for f in ["cognishift_demo_ca.crt", "cognishift_demo_ca.key", "server_cert.pem", "server_key.pem"]:
            p = outdir / f
            if p.exists():
                p.unlink()

    ca_cert, srv_cert, srv_key = ensure_local_tls_certificates(
        cert_dir=outdir,
        server_ips=ips,
        server_hostnames=hostnames,
    )
    validate_tls_pair(srv_cert, srv_key)
    names, cert_ips = get_cert_sans(srv_cert)
    print(f"[SUCCESS] Local CA Certificate: {ca_cert}")
    print(f"[SUCCESS] Server Certificate:   {srv_cert}")
    print(f"[SUCCESS] Server Private Key:   {srv_key}")
    print(f"[SUCCESS] Certificate SANs:     Hostnames={names}, IPs={cert_ips}")
    print("[SUCCESS] Uvicorn SSL certificate/key load validation passed.")


if __name__ == "__main__":
    main()
