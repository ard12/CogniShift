"""
Fine-Grained Retrieval Latency & Execution Profiler for CogniShift.
Instruments stage-by-stage latencies:
- Query Tokenization & Embedding
- Vector Load / Memory Retrieval
- Late-Interaction MaxSim Computation
- Metadata & Version Filtering
- Evidence Fusion (RRF / Confidence Gating)
- Bounded VLM Inspection
- Total End-to-End Query-to-Evidence Latency

Enforces strict separation between COLD, WARM_UNCACHED, WARM_CACHED, and FUSION_ONLY executions.
"""
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class StageTiming:
    query_embedding_ms: float = 0.0
    vector_load_ms: float = 0.0
    maxsim_ms: float = 0.0
    filtering_ms: float = 0.0
    fusion_ms: float = 0.0
    vlm_inspection_ms: float = 0.0
    total_e2e_ms: float = 0.0
    mode: str = "warm_uncached"  # 'cold', 'warm_uncached', 'warm_cached', 'fusion_only'
    channel: str = "hybrid"      # 'text_only', 'visual_only', 'hybrid'
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_embedding_ms": round(self.query_embedding_ms, 2),
            "vector_load_ms": round(self.vector_load_ms, 2),
            "maxsim_ms": round(self.maxsim_ms, 2),
            "filtering_ms": round(self.filtering_ms, 2),
            "fusion_ms": round(self.fusion_ms, 2),
            "vlm_inspection_ms": round(self.vlm_inspection_ms, 2),
            "total_e2e_ms": round(self.total_e2e_ms, 2),
            "mode": self.mode,
            "channel": self.channel,
            **self.metadata
        }


class LatencyProfiler:
    """Context manager and tracker for end-to-end and stage-level timing."""

    def __init__(self, channel: str = "hybrid", mode: str = "warm_uncached"):
        self.timing = StageTiming(channel=channel, mode=mode)
        self._t_start = 0.0
        self._stage_start = 0.0
        self._active_stage: Optional[str] = None

    def __enter__(self):
        self._t_start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.timing.total_e2e_ms = (time.perf_counter() - self._t_start) * 1000.0

    def start_stage(self, stage_name: str):
        self._active_stage = stage_name
        self._stage_start = time.perf_counter()

    def end_stage(self, stage_name: str) -> float:
        dt = (time.perf_counter() - self._stage_start) * 1000.0
        if stage_name == "query_embedding":
            self.timing.query_embedding_ms += dt
        elif stage_name == "vector_load":
            self.timing.vector_load_ms += dt
        elif stage_name == "maxsim":
            self.timing.maxsim_ms += dt
        elif stage_name == "filtering":
            self.timing.filtering_ms += dt
        elif stage_name == "fusion":
            self.timing.fusion_ms += dt
        elif stage_name == "vlm_inspection":
            self.timing.vlm_inspection_ms += dt
        self._active_stage = None
        return dt
