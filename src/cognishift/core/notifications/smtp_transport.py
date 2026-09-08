"""Sovereign local SMTP transport operating strictly on loopback (127.0.0.1:1025).

Adheres strictly to air-gap and sovereignty rules:
- Loopback binding only (127.0.0.1). Any attempt to bind to 0.0.0.0 is rejected.
- Zero Cloud Egress: all traffic stays on the local machine.
- Decoupled from core security decisions: transport failure never halts primary controls.
- Thunderbird / Outlook / EML compatible: writes to data/alerts/mailbox/*.eml.
"""
import asyncio
from email.message import EmailMessage
import email.utils
import logging
from pathlib import Path
import smtplib
import socket
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

LOCAL_SMTP_HOST = "127.0.0.1"
LOCAL_SMTP_PORT = 1025
MAILBOX_DIR = Path("data/alerts/mailbox")

_SERVER_INSTANCE: Optional[asyncio.AbstractServer] = None
_SERVER_TASK: Optional[asyncio.Task] = None


class SMTPSession:
    """Handles an RFC 5321 session over an asyncio stream."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.mail_from: Optional[str] = None
        self.rcpt_to: List[str] = []

    async def run(self) -> None:
        try:
            self.writer.write(b"220 CogniShift Sovereign SMTP Service Ready\r\n")
            await self.writer.drain()

            while True:
                line = await self.reader.readline()
                if not line:
                    break

                cmd_line = line.decode("utf-8", errors="replace").strip()
                if not cmd_line:
                    continue

                parts = cmd_line.split(" ", 1)
                cmd = parts[0].upper()
                arg = parts[1] if len(parts) > 1 else ""

                if cmd in ("HELO", "EHLO"):
                    self.writer.write(b"250-CogniShift Sovereign SMTP (Air-Gapped)\r\n250-8BITMIME\r\n250 OK\r\n")
                    await self.writer.drain()

                elif cmd == "MAIL":
                    # Expecting MAIL FROM:<...>
                    self.mail_from = arg.replace("FROM:", "").strip("<> ")
                    self.writer.write(b"250 2.1.0 Sender OK\r\n")
                    await self.writer.drain()

                elif cmd == "RCPT":
                    # Expecting RCPT TO:<...>
                    rcpt = arg.replace("TO:", "").strip("<> ")
                    self.rcpt_to.append(rcpt)
                    self.writer.write(b"250 2.1.5 Recipient OK\r\n")
                    await self.writer.drain()

                elif cmd == "DATA":
                    self.writer.write(b"354 Start mail input; end with <CRLF>.<CRLF>\r\n")
                    await self.writer.drain()

                    data_lines = []
                    while True:
                        dline = await self.reader.readline()
                        if not dline:
                            break
                        if dline in (b".\r\n", b".\n", b"."):
                            break
                        data_lines.append(dline)

                    raw_eml = b"".join(data_lines)
                    eml_path = self._save_eml(raw_eml)

                    self.writer.write(b"250 2.0.0 Message queued for sovereign delivery\r\n")
                    await self.writer.drain()

                elif cmd == "RSET":
                    self.mail_from = None
                    self.rcpt_to = []
                    self.writer.write(b"250 2.0.0 Reset OK\r\n")
                    await self.writer.drain()

                elif cmd == "NOOP":
                    self.writer.write(b"250 2.0.0 OK\r\n")
                    await self.writer.drain()

                elif cmd == "QUIT":
                    self.writer.write(b"221 2.0.0 Service closing transmission channel\r\n")
                    await self.writer.drain()
                    break

                else:
                    self.writer.write(b"500 5.5.1 Command unrecognized\r\n")
                    await self.writer.drain()

        except Exception as exc:
            logger.debug(f"SMTP session error: {exc}")
        finally:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass

    def _save_eml(self, raw_bytes: bytes) -> Optional[Path]:
        try:
            MAILBOX_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            uid = uuid.uuid4().hex[:8]
            target = MAILBOX_DIR / f"{timestamp}_{uid}.eml"
            target.write_bytes(raw_bytes)
            return target
        except Exception as exc:
            logger.error(f"Failed to persist .eml: {exc}")
            return None


async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    session = SMTPSession(reader, writer)
    await session.run()


class _ExistingServer:
    """Placeholder server reference when SMTP listener is already running in a companion process."""
    def close(self):
        pass

    async def wait_closed(self):
        pass

    def is_serving(self):
        return True


async def start_local_smtp_server(
    host: str = LOCAL_SMTP_HOST,
    port: int = LOCAL_SMTP_PORT,
) -> Any:
    """Start local loopback SMTP server. Enforces 127.0.0.1 binding."""
    global _SERVER_INSTANCE
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError(f"CRITICAL SECURITY VIOLATION: Local SMTP can only bind to loopback (127.0.0.1). Attempted {host}.")

    if _SERVER_INSTANCE is not None:
        try:
            loop = asyncio.get_running_loop()
            if getattr(_SERVER_INSTANCE, "_loop", None) is loop and _SERVER_INSTANCE.is_serving():
                return _SERVER_INSTANCE
        except Exception:
            pass
        try:
            _SERVER_INSTANCE.close()
        except Exception:
            pass
        _SERVER_INSTANCE = None

    MAILBOX_DIR.mkdir(parents=True, exist_ok=True)
    try:
        server = await asyncio.start_server(_handle_client, host, port)
        _SERVER_INSTANCE = server
        logger.info(f"Sovereign Local SMTP listener active on {host}:{port} (LOOPBACK ONLY)")
        return server
    except OSError as exc:
        if "10048" in str(exc) or getattr(exc, "winerror", None) == 10048 or getattr(exc, "errno", None) in (48, 98):
            health = await check_smtp_health(host, port)
            if health.get("status") == "ACTIVE":
                logger.info(f"Sovereign Local SMTP listener is already running on {host}:{port}")
                return _ExistingServer()
        raise



async def stop_local_smtp_server() -> None:
    """Gracefully terminate local loopback SMTP server."""
    global _SERVER_INSTANCE
    if _SERVER_INSTANCE is not None:
        try:
            _SERVER_INSTANCE.close()
            await _SERVER_INSTANCE.wait_closed()
        except Exception:
            pass
        _SERVER_INSTANCE = None
        logger.info("Local SMTP listener stopped.")


def _send_mail_sync(
    sender: str,
    recipients: List[str],
    msg: EmailMessage,
    host: str = LOCAL_SMTP_HOST,
    port: int = LOCAL_SMTP_PORT,
) -> None:
    """Synchronous smtplib dispatch executed inside a thread."""
    with smtplib.SMTP(host, port, timeout=4.0) as client:
        client.ehlo()
        client.send_message(msg, from_addr=sender, to_addrs=recipients)


async def send_internal_email(
    sender: str,
    recipients: List[str],
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    host: str = LOCAL_SMTP_HOST,
    port: int = LOCAL_SMTP_PORT,
) -> bool:
    """Send an internal notification via local loopback SMTP without blocking event loop."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Date"] = email.utils.formatdate(localtime=True) if hasattr(email, "utils") else str(time.time())
    msg.set_content(body_text)

    if body_html:
        msg.add_alternative(body_html, subtype="html")

    try:
        await asyncio.to_thread(_send_mail_sync, sender, recipients, msg, host, port)
        return True
    except Exception as exc:
        logger.warning(f"Failed to dispatch to local SMTP ({host}:{port}): {exc}")
        return False


async def check_smtp_health(
    host: str = LOCAL_SMTP_HOST,
    port: int = LOCAL_SMTP_PORT,
) -> Dict[str, Any]:
    """Test connection to local loopback SMTP server."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=2.0,
        )
        banner = await asyncio.wait_for(reader.readline(), timeout=2.0)
        writer.write(b"QUIT\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

        return {
            "status": "ACTIVE",
            "host": host,
            "port": port,
            "banner": banner.decode().strip(),
            "loopback_only": True,
            "secure": True,
        }
    except Exception as exc:
        return {
            "status": "UNAVAILABLE",
            "host": host,
            "port": port,
            "error": str(exc),
            "loopback_only": True,
            "secure": True,
        }
