import pytest
from httpx import ASGITransport, AsyncClient

from cognishift.app.main import app


@pytest.mark.asyncio
async def test_static_and_root_serving():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        root_res = await client.get("/", follow_redirects=False)
        assert root_res.status_code == 307
        assert root_res.headers["location"] == "/static/index.html"

        index_res = await client.get("/static/index.html")
        assert index_res.status_code == 200
        assert "Content-Security-Policy" in index_res.headers
        assert "script-src 'self'" in index_res.headers["Content-Security-Policy"]
        assert '<script src="/static/app.js' in index_res.text
        assert 'defer></script>' in index_res.text
        assert "<script>" not in index_res.text

        js_res = await client.get("/static/app.js")
        assert js_res.status_code == 200
        assert len(js_res.text) > 1000

        css_res = await client.get("/static/app.css")
        assert css_res.status_code == 200
        assert len(css_res.text) > 1000
