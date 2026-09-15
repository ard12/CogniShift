import pytest
from httpx import ASGITransport, AsyncClient
from pathlib import Path

from cognishift.app.main import app
from cognishift.app.config import settings, PROJECT_ROOT


@pytest.mark.asyncio
async def test_root_and_frontend_serving():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        root_res = await client.get("/", follow_redirects=False)
        assert root_res.status_code == 200
        assert "Content-Security-Policy" in root_res.headers
        assert "script-src 'self'" in root_res.headers["Content-Security-Policy"]
        assert "img-src 'self' data: blob:" in root_res.headers["Content-Security-Policy"]

        vite_dist = PROJECT_ROOT / "frontend" / "dist" / "index.html"

        if vite_dist.exists():
            assert "<!doctype html>" in root_res.text.lower()
        else:
            data = root_res.json()
            assert data["app"] == "CogniShift API"
            assert data["status"] == "online"
