"""Phase 6 Tier C: Independent Host Network Observation Tests.

Verifies the independent network observer using an executable negative control
and confirms zero unauthorized egress during actual local inference and retrieval.
"""

import os
import sys
import pytest

from scripts.observe_network import NetworkObserver, run_negative_control
from cognishift.core.network.client import get_sovereign_async_client
from cognishift.app.config import settings
from cognishift.core.retriever import embedding_model


def test_observer_negative_control():
    """Negative Control: Proves the observer detects socket events when they occur."""
    result = run_negative_control()
    assert result is True, "Negative control failed: Observer did not detect active socket!"


@pytest.mark.asyncio
async def test_strict_workflow_records_zero_unauthorized_egress():
    """Verify that a full local inference & embedding workflow produces zero unauthorized egress."""
    observer = NetworkObserver(target_pids=[os.getpid()], sample_interval=0.01)
    observer.start()

    try:
        # 1. Local Ollama call via sovereign client
        async with get_sovereign_async_client(component="observation_test") as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            assert resp.status_code == 200

        # 2. Local FastEmbed embedding generation
        vectors = list(embedding_model.embed(["Industrial compressor pressure test"]))
        assert len(vectors) == 1
        assert len(vectors[0]) == 384

    finally:
        observer.stop()

    summary = observer.get_summary()

    # Verify zero unauthorized connections
    assert summary["unauthorized_count"] == 0, f"Unauthorized connections detected: {summary['unauthorized_violations']}"
    assert summary["public_count"] == 0, "Public connections detected during sovereign workflow!"
    assert summary["link_local_count"] == 0, "Link-local connections detected!"

    # Verify that the observer method passes without exception
    observer.assert_zero_unauthorized_egress()
