#!/usr/bin/env python3
"""Start CogniShift HTTPS with a bounded retry for transient Windows PEM reads."""
from __future__ import annotations

import argparse
import ssl
import time

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CogniShift TLS server.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--ssl-keyfile", required=True)
    parser.add_argument("--ssl-certfile", required=True)
    args = parser.parse_args()

    for attempt in range(1, 4):
        try:
            uvicorn.run(
                "cognishift.app.main:app",
                app_dir="src",
                host=args.host,
                port=args.port,
                ssl_keyfile=args.ssl_keyfile,
                ssl_certfile=args.ssl_certfile,
            )
            return
        except ssl.SSLError as exc:
            if "PEM lib" not in str(exc) or attempt == 3:
                raise
            delay = attempt
            print(
                f"[WARNING] Windows could not read the refreshed PEM pair "
                f"(attempt {attempt}/3). Retrying in {delay}s...",
                flush=True,
            )
            time.sleep(delay)


if __name__ == "__main__":
    main()
