#!/usr/bin/env python3
"""CLI utility to generate or regenerate local TLS certificates for LAN deployment."""
import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import socket
from cognishift.app.core.tls import ensure_local_tls_certificates, get_default_cert_dir, get_cert_sans


def detect_host_ips() -> list[str]:
    """Detect non-loopback, non-link-local IPv4 addresses on host network adapters."""
    detected = ["127.0.0.1", "10.10.182.228"]
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
    names, cert_ips = get_cert_sans(srv_cert)
    print(f"[SUCCESS] Local CA Certificate: {ca_cert}")
    print(f"[SUCCESS] Server Certificate:   {srv_cert}")
    print(f"[SUCCESS] Server Private Key:   {srv_key}")
    print(f"[SUCCESS] Certificate SANs:     Hostnames={names}, IPs={cert_ips}")


if __name__ == "__main__":
    main()
