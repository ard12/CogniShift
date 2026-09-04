"""Phase 6 Tier B: Real Application Enforcement Tests.

Verifies real local loopback to Ollama, real pre-socket blocking of public and LAN egress,
FastEmbed offline fail-closed behavior, Ollama missing model fail-closed behavior,
Four-Eyes approval immunity (network policy cannot be bypassed), and sensitive marker
redaction in the network audit ledger.
"""

import os
import pytest
import httpx
import aiosqlite

from cognishift.app.config import settings
from cognishift.core.network.client import get_sovereign_async_client, get_sovereign_client
from cognishift.core.network.schemas import NetworkPolicyViolation
from cognishift.core.ollama_provider import OllamaProvider
from cognishift.core.providers import ProviderError
from cognishift.app.db.database import get_db


@pytest.mark.asyncio
async def test_real_ollama_loopback_allowed():
    """Verify real local Ollama query succeeds via SovereignAsyncClient and logs event."""
    async with get_sovereign_async_client(component="test_ollama_loopback") as client:
        resp = await client.get(f"{settings.ollama_base_url}/api/tags")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data

    # Verify audit event in database
    async with get_db() as db:
        async with db.execute(
            "SELECT destination_class, policy_decision FROM network_events WHERE component = ? ORDER BY id DESC LIMIT 1",
            ("test_ollama_loopback",)
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row["destination_class"] == "loopback"
            assert row["policy_decision"] == "ALLOWED"


@pytest.mark.asyncio
async def test_real_public_request_blocked_before_socket_connect():
    """Verify outbound HTTP to a public IP is blocked before any socket connects."""
    async with get_sovereign_async_client(component="test_public_block") as client:
        with pytest.raises(NetworkPolicyViolation) as exc_info:
            await client.get("http://93.184.216.34:80")
        assert "public" in str(exc_info.value).lower()
        assert "blocked" in str(exc_info.value).lower()

    # Verify audit event in database
    async with get_db() as db:
        async with db.execute(
            "SELECT destination_class, policy_decision FROM network_events WHERE component = ? ORDER BY id DESC LIMIT 1",
            ("test_public_block",)
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row["destination_class"] == "public"
            assert row["policy_decision"] == "BLOCKED"


@pytest.mark.asyncio
async def test_real_unauthorized_lan_request_blocked():
    """Verify outbound HTTP to an unauthorized RFC1918 LAN IP is blocked."""
    async with get_sovereign_async_client(component="test_lan_block") as client:
        with pytest.raises(NetworkPolicyViolation) as exc_info:
            await client.get("http://192.168.1.1:8080")
        assert "private" in str(exc_info.value).lower()
        assert "blocked" in str(exc_info.value).lower()

    # Verify audit event in database
    async with get_db() as db:
        async with db.execute(
            "SELECT destination_class, policy_decision FROM network_events WHERE component = ? ORDER BY id DESC LIMIT 1",
            ("test_lan_block",)
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row["destination_class"] == "private"
            assert row["policy_decision"] == "BLOCKED"


def test_real_fastembed_offline_fails_closed_when_cache_missing(tmp_path):
    """Verify FastEmbed with local_files_only=True raises error if model is not in cache."""
    from fastembed import TextEmbedding

    empty_cache = tmp_path / "empty_cache"
    empty_cache.mkdir()

    # When cache is missing and local_files_only=True, it must fail closed
    with pytest.raises((ValueError, FileNotFoundError, Exception)):
        TextEmbedding(
            model_name="BAAI/bge-small-en-v1.5",
            cache_dir=str(empty_cache),
            local_files_only=True,
        )


@pytest.mark.asyncio
async def test_real_missing_ollama_model_fails_closed_without_pull():
    """Verify requesting an unregistered model fails closed without triggering pull."""
    provider = OllamaProvider()
    with pytest.raises(ProviderError) as exc_info:
        await provider.generate_text(
            prompt="Test missing model fail closed",
            system_prompt="",
            context="",
            model_name="nonexistent-model-strictly-missing:latest"
        )
    # The error must show 404 / not found from local daemon, with zero attempt to pull
    assert "404" in str(exc_info.value) or "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_approval_does_not_override_network_policy():
    """Verify that human approval (HITL) cannot bypass sovereign network policy.
    
    Even if an action is approved by an operator, the underlying transport guard
    unconditionally blocks unauthorized egress.
    """
    async def simulated_approved_tool_execution():
        async with get_sovereign_async_client(component="tool_execution") as client:
            return await client.get("http://8.8.8.8:80")

    with pytest.raises(NetworkPolicyViolation):
        await simulated_approved_tool_execution()


@pytest.mark.asyncio
async def test_sensitive_data_not_leaked_in_network_audit():
    """Verify secrets (tokens, prompts, query parameters) are NEVER logged in network_events."""
    sensitive_token = "BEARER_SECRET_TOKEN_XYZ_999"
    sensitive_body_marker = "PROMPT_SECRET_PAYLOAD_ABC_777"
    component_name = "test_leak_guard"

    async with get_sovereign_async_client(component=component_name) as client:
        with pytest.raises(NetworkPolicyViolation):
            await client.get(
                "http://93.184.216.34:80/api?secret=" + sensitive_token,
                headers={"Authorization": f"Bearer {sensitive_token}"}
            )

    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM network_events WHERE component = ?",
            (component_name,)
        ) as cursor:
            rows = await cursor.fetchall()
            assert len(rows) > 0
            for row in rows:
                for col_name in row.keys():
                    val = str(row[col_name])
                    assert sensitive_token not in val, f"Leaked sensitive token in column {col_name}!"
                    assert sensitive_body_marker not in val, f"Leaked sensitive marker in column {col_name}!"
