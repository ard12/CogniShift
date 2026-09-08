import pytest
from httpx import ASGITransport, AsyncClient

from cognishift.app.main import app


@pytest.mark.asyncio
async def test_spa_history_routes_refresh_to_index_without_masking_api_404s():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        security = await client.get("/security")
        assert security.status_code == 200
        assert "text/html" in security.headers.get("content-type", "")
        assert "CogniShift" in security.text

        mailbox = await client.get("/mailbox")
        assert mailbox.status_code == 200
        assert "text/html" in mailbox.headers.get("content-type", "")
        assert "CogniShift" in mailbox.text

        missing_api = await client.get("/api/v1/does-not-exist")
        assert missing_api.status_code == 404
        assert missing_api.headers.get("content-type", "").startswith("application/json")

        unknown_file = await client.get("/favicon-does-not-exist.svg")
        assert unknown_file.status_code == 404
