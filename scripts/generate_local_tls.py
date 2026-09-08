#!/usr/bin/env python3
"""CLI utility to generate or regenerate local TLS certificates for LAN deployment."""
import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cognishift.app.core.tls import ensure_local_tls_certificates, get_default_cert_dir


def main():
    parser = argparse.ArgumentParser(description="Generate local TLS CA and Server certificates.")
    parser.add_argument("--ip", action="append", default=["10.10.182.228", "127.0.0.1"], help="Server IP address for SAN")
    parser.add_argument("--hostname", action="append", default=["localhost"], help="Server hostname for SAN")
    parser.add_argument("--outdir", default=None, help="Output directory for certificates")
    parser.add_argument("--force", action="store_true", help="Force regenerate certificates")

    args = parser.parse_args()
    outdir = Path(args.outdir) if args.outdir else get_default_cert_dir()

    if args.force:
        for f in ["cognishift_demo_ca.crt", "cognishift_demo_ca.key", "server_cert.pem", "server_key.pem"]:
            p = outdir / f
            if p.exists():
                p.unlink()

    ca_cert, srv_cert, srv_key = ensure_local_tls_certificates(
        cert_dir=outdir,
        server_ips=list(set(args.ip)),
        server_hostnames=list(set(args.hostname)),
    )
    print(f"[SUCCESS] Local CA Certificate: {ca_cert}")
    print(f"[SUCCESS] Server Certificate:   {srv_cert}")
    print(f"[SUCCESS] Server Private Key:   {srv_key}")


if __name__ == "__main__":
    main()
