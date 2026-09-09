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

        operator = await client.get("/operator")
        assert operator.status_code == 200
        assert "text/html" in operator.headers.get("content-type", "")

        dashboard = await client.get("/dashboard")
        assert dashboard.status_code == 200
        assert "text/html" in dashboard.headers.get("content-type", "")

        favicon = await client.get("/favicon.svg")
        assert favicon.status_code == 200
        assert favicon.headers.get("content-type", "").startswith("image/svg+xml")

        missing_api = await client.get("/api/v1/does-not-exist")
        assert missing_api.status_code == 404
        assert missing_api.headers.get("content-type", "").startswith("application/json")

        unknown_file = await client.get("/favicon-does-not-exist.svg")
        assert unknown_file.status_code == 404


@pytest.mark.asyncio
async def test_private_hotspot_origin_is_allowed_by_cors():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/v1/workspaces",
            headers={
                "Origin": "https://192.168.43.50:8443",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://192.168.43.50:8443"


@pytest.mark.asyncio
async def test_public_and_non_rfc1918_172_origins_are_not_allowed_by_cors():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for origin in ("https://192.0.2.20:8443", "https://172.15.1.20:8443"):
            response = await client.options(
                "/api/v1/workspaces",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert response.status_code == 400
            assert "access-control-allow-origin" not in response.headers
