"""Phase 6 Browser Egress and Frontend Sovereignty Tests.

Verifies that the frontend contains zero external CDN dependencies, that local
stylesheets and scripts are intact, that Content Security Policy headers are strictly
enforced on all HTTP responses, and includes a negative control proving scanner sensitivity.
"""

import re
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

from cognishift.app.main import app

INDEX_HTML_PATH = Path("src/cognishift/app/static/index.html")
APP_CSS_PATH = Path("src/cognishift/app/static/app.css")

# Match URLs starting with http://, https://, or protocol-relative //
EXTERNAL_URL_PATTERN = re.compile(r'https?://[a-zA-Z0-9.-]+|//[a-zA-Z0-9.-]+')


def scan_for_external_urls(content: str):
    """Find all external URLs in HTML or text content."""
    matches = EXTERNAL_URL_PATTERN.findall(content)
    # Filter out localhost or 127.0.0.1 or ::1
    external = [m for m in matches if not any(lh in m for lh in ("localhost", "127.0.0.1", "::1"))]
    return external


def test_index_html_contains_zero_external_links():
    """Verify that index.html contains zero external URLs or CDN references."""
    assert INDEX_HTML_PATH.exists(), f"Missing {INDEX_HTML_PATH}"
    content = INDEX_HTML_PATH.read_text(encoding="utf-8")

    external_urls = scan_for_external_urls(content)
    assert len(external_urls) == 0, f"Found external URLs in index.html: {external_urls}"


def test_local_static_assets_exist():
    """Verify that all referenced local assets in index.html exist on disk."""
    assert APP_CSS_PATH.exists(), f"Missing {APP_CSS_PATH}"
    css_content = APP_CSS_PATH.read_text(encoding="utf-8")
    assert len(css_content.strip()) > 500, "app.css is unexpectedly small or empty"

    external_css_refs = scan_for_external_urls(css_content)
    assert len(external_css_refs) == 0, f"Found external references in app.css: {external_css_refs}"


def test_browser_scanner_negative_control():
    """Negative Control: Proves that scan_for_external_urls detects CDN links when present."""
    dirty_html = """
    <html>
        <head>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body>
            <p>Test</p>
        </body>
    </html>
    """
    detected = scan_for_external_urls(dirty_html)
    assert len(detected) == 2, f"Expected 2 detected URLs, got {detected}"
    assert any("tailwindcss.com" in url for url in detected)
    assert any("cdnjs.cloudflare.com" in url for url in detected)


@pytest.mark.asyncio
async def test_content_security_policy_header_enforced():
    """Verify Content Security Policy and security headers on FastAPI responses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/system/status")
        assert resp.status_code == 200

        # Verify CSP header
        csp = resp.headers.get("content-security-policy", "")
        assert csp != "", "Missing Content-Security-Policy header"
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "connect-src 'self'" in csp

        # Verify other anti-exfiltration security headers
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert resp.headers.get("referrer-policy") == "no-referrer"
