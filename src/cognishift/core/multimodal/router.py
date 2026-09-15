"""
Multimodal Model Router for CogniShift.
Manages profile resolution (FAST -> 2B, DEEP -> 7B), local inventory verification,
strict structured schema extraction, fail-closed offline execution, and audit telemetry.
"""
import time
import json
import re
import hashlib
import logging
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from cognishift.app.config import settings
from cognishift.core.multimodal.schemas import (
    MultimodalModelProfile,
    MultimodalModelConfig,
    MultimodalInferenceResult,
    StructuredVisualObservation,
    VisualRelationItem
)
from cognishift.core.network.client import get_sovereign_async_client
from cognishift.core.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)

TAG_RE = re.compile(r"\b([A-Za-z]{1,4}-\d{2,4}[A-Za-z]?)\b")


class MultimodalModelRouter:
    """
    Authoritative visual inference router for CogniShift.
    Resolves FAST and DEEP profiles to local sovereign models, enforces structured
    contracts separate from task questions, and guarantees fail-closed execution.
    """

    def __init__(self, provider: Optional[OllamaProvider] = None):
        self.provider = provider or OllamaProvider()
        self._inventory_cache: Optional[List[str]] = None
        self._inventory_timestamp: float = 0.0
        self._inventory_ttl: float = 60.0

    def resolve_profile_model(self, profile: MultimodalModelProfile) -> Tuple[str, Optional[str], bool]:
        """
        Resolves a typed profile to configured local model tag and fallback.
        Returns (primary_model_tag, fallback_model_tag, allow_fallback).
        """
        allow_fallback = getattr(settings, "multimodal_allow_fallback", False)
        if profile == MultimodalModelProfile.FAST:
            primary = getattr(settings, "qwen2_vl_fast_model", "qwen2-vl:2b")
            fallback = getattr(settings, "qwen2_vl_deep_model", "qwen2-vl:7b") if allow_fallback else None
        else:
            primary = getattr(settings, "qwen2_vl_deep_model", "qwen2-vl:7b")
            fallback = getattr(settings, "qwen2_vl_fast_model", "qwen2-vl:2b") if allow_fallback else None
        return primary, fallback, allow_fallback

    async def get_local_inventory(self, force_refresh: bool = False) -> List[str]:
        """
        Queries the local Ollama inventory offline.
        Never executes auto-pull or internet requests.
        """
        now = time.monotonic()
        if not force_refresh and self._inventory_cache is not None and (now - self._inventory_timestamp) < self._inventory_ttl:
            return list(self._inventory_cache)

        tags = []
        try:
            base_url = getattr(settings, "ollama_base_url", "http://127.0.0.1:11434").rstrip("/")
            async with get_sovereign_async_client(timeout=5.0, component="multimodal_router") as client:
                resp = await client.get(f"{base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    for m in data.get("models", []):
                        name = m.get("name", "")
                        if name:
                            tags.append(name)
                            # Also register base tag if colon exists
                            if ":" in name:
                                tags.append(name.split(":")[0])
        except Exception as e:
            logger.warning(f"Could not reach local Ollama inventory at {base_url}: {e}")

        self._inventory_cache = tags
        self._inventory_timestamp = now
        return list(tags)

    def is_model_installed(self, model_tag: str, inventory: List[str]) -> bool:
        """Checks if a model tag or alias exists in local inventory."""
        clean = model_tag.strip().lower()
        inv_lower = [t.lower() for t in inventory]
        if clean in inv_lower:
            return True
        if ":" not in clean:
            # Untagged model identifier - match exact base or base:latest or first available variant
            if f"{clean}:latest" in inv_lower or any(t.split(":")[0] == clean for t in inv_lower):
                return True
        else:
            base, tag = clean.split(":", 1)
            if tag == "latest" and (base in inv_lower or any(t.split(":")[0] == base for t in inv_lower)):
                return True
        return False

    async def detect_running_device(self, model_name: str) -> str:
        """
        Queries Ollama /api/ps to inspect device/GPU offload for active model.
        Returns 'GPU', 'CPU', or 'UNKNOWN'. Never fabricates.
        """
        try:
            base_url = getattr(settings, "ollama_base_url", "http://127.0.0.1:11434").rstrip("/")
            async with get_sovereign_async_client(timeout=3.0, component="multimodal_router") as client:
                resp = await client.get(f"{base_url}/api/ps")
                if resp.status_code == 200:
                    data = resp.json()
                    for m in data.get("models", []):
                        if model_name.lower() in m.get("name", "").lower():
                            size_vram = m.get("size_vram", 0)
                            if size_vram > 0:
                                return "GPU"
                            elif m.get("size", 0) > 0:
                                return "CPU"
        except Exception:
            pass
        return "UNKNOWN"

    def build_inference_prompt(self, task_query: str) -> str:
        """
        Strictly separates the task-specific question from the structured output contract.
        Prevents prompt injection and query-wording hallucination.
        """
        clean_task = (task_query or "").strip()
        if not clean_task:
            clean_task = "Analyze this engineering diagram, document, or slide image. Identify visible tagged equipment, instruments, process lines, and observations."

        contract_prompt = (
            f"[TASK INSTRUCTION]\n"
            f"{clean_task}\n\n"
            f"[STRUCTURED OUTPUT CONTRACT]\n"
            f"Inspect the image carefully. You must return valid machine-readable JSON adhering strictly to this schema:\n"
            f"```json\n"
            f"{{\n"
            f'  "observed_equipment_tags": ["<equipment tag like P-101A, K-201, HEX-102>"],\n'
            f'  "observed_instrument_tags": ["<instrument tag like PT-101, TT-201, FV-302>"],\n'
            f'  "observed_relations": [\n'
            f'    {{\n'
            f'      "subject": "<tag>",\n'
            f'      "relation_type": "UPSTREAM_OF|DOWNSTREAM_OF|CONNECTED_TO",\n'
            f'      "object": "<tag>",\n'
            f'      "evidence_basis": "<visible basis like line arrow, process connection>"\n'
            f'    }}\n'
            f'  ],\n'
            f'  "numeric_claims": [\n'
            f'    {{"item": "<description>", "value": "<numeric value>", "unit": "<unit>"}}\n'
            f'  ],\n'
            f'  "visual_observations": ["<concise factual observation>"]\n'
            f"}}\n"
            f"```\n"
            f"CRITICAL RULES:\n"
            f"1. Only report equipment, tags, numbers, and relationships that are visibly present in the image.\n"
            f"2. Do not infer direction or equipment presence from the task instruction or query wording.\n"
            f"3. Return valid JSON only."
        )
        return contract_prompt

    def parse_structured_output(self, raw_text: str) -> Tuple[StructuredVisualObservation, bool]:
        """
        Parses machine-readable JSON output strictly into StructuredVisualObservation.
        Returns (StructuredVisualObservation, is_valid).
        If JSON is missing or malformed, returns an empty observation with is_valid=False.
        """
        if not raw_text or not raw_text.strip():
            return StructuredVisualObservation(), False

        parsed_json = None
        try:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
            if match:
                parsed_json = json.loads(match.group(1))
            else:
                match2 = re.search(r"(\{.*\})", raw_text, re.DOTALL)
                if match2:
                    parsed_json = json.loads(match2.group(1))
                else:
                    parsed_json = json.loads(raw_text.strip())
        except Exception:
            parsed_json = None

        if not isinstance(parsed_json, dict):
            return StructuredVisualObservation(), False

        eq_tags: List[str] = []
        for tag in parsed_json.get("observed_equipment_tags", parsed_json.get("equipment_tags", [])):
            if isinstance(tag, str) and tag.strip():
                eq_tags.append(tag.strip().upper())

        inst_tags: List[str] = []
        for tag in parsed_json.get("observed_instrument_tags", parsed_json.get("instrument_tags", [])):
            if isinstance(tag, str) and tag.strip():
                inst_tags.append(tag.strip().upper())

        relations: List[VisualRelationItem] = []
        raw_rels = parsed_json.get("observed_relations", parsed_json.get("relations", []))
        if isinstance(raw_rels, list):
            for rel in raw_rels:
                if isinstance(rel, dict) and "subject" in rel and "object" in rel:
                    subj = str(rel["subject"]).strip().upper()
                    obj = str(rel["object"]).strip().upper()
                    rel_type = str(rel.get("relation_type", "CONNECTED_TO")).strip().upper()
                    if rel_type not in ("UPSTREAM_OF", "DOWNSTREAM_OF", "CONNECTED_TO"):
                        rel_type = "CONNECTED_TO"
                    basis = str(rel.get("evidence_basis", "")).strip()
                    if subj and obj:
                        relations.append(VisualRelationItem(
                            subject=subj,
                            relation_type=rel_type,
                            object=obj,
                            evidence_basis=basis
                        ))

        num_claims: List[Dict[str, Any]] = []
        for nc in parsed_json.get("numeric_claims", []):
            if isinstance(nc, dict):
                num_claims.append(nc)

        vis_obs: List[str] = []
        for vo in parsed_json.get("visual_observations", []):
            if isinstance(vo, str) and vo.strip():
                vis_obs.append(vo.strip())

        obs = StructuredVisualObservation(
            observed_equipment_tags=list(dict.fromkeys(eq_tags)),
            observed_instrument_tags=list(dict.fromkeys(inst_tags)),
            observed_relations=relations,
            numeric_claims=num_claims,
            visual_observations=vis_obs
        )
        return obs, True

    async def inspect_image(
        self,
        image_bytes: bytes,
        profile: Optional[MultimodalModelProfile] = None,
        task_query: str = "",
        model_override: Optional[str] = None
    ) -> MultimodalInferenceResult:
        """
        Executes end-to-end multimodal image inspection.
        Enforces profile routing, local inventory verification, latency tracking,
        strict structured schema parsing, and honest failure reporting.
        """
        t0 = time.perf_counter()
        req_profile = profile or MultimodalModelProfile(getattr(settings, "multimodal_profile", "fast").lower())
        image_sha = hashlib.sha256(image_bytes).hexdigest()

        # 1. Resolve primary model and fallback configuration
        if model_override:
            primary_tag = model_override
            fallback_tag = None
            allow_fallback = False
        else:
            primary_tag, fallback_tag, allow_fallback = self.resolve_profile_model(req_profile)

        # 2. Check local inventory offline (ZERO AUTO-PULL)
        inventory = await self.get_local_inventory()
        target_model = primary_tag
        fallback_used = False
        fallback_reason = None
        actual_profile = req_profile

        if not self.is_model_installed(primary_tag, inventory):
            # Primary model is absent in local Ollama inventory
            if allow_fallback and fallback_tag and self.is_model_installed(fallback_tag, inventory):
                target_model = fallback_tag
                fallback_used = True
                actual_profile = MultimodalModelProfile.FAST if req_profile == MultimodalModelProfile.DEEP else MultimodalModelProfile.DEEP
                fallback_reason = f"Primary model '{primary_tag}' not installed in local Ollama; using configured fallback '{fallback_tag}'."
                logger.info(fallback_reason)
            else:
                latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                fail_msg = f"MODEL_UNAVAILABLE: Configured vision model '{primary_tag}' is not installed in local Ollama inventory."
                logger.warning(fail_msg)
                return MultimodalInferenceResult(
                    requested_profile=req_profile,
                    actual_profile=actual_profile,
                    requested_model=primary_tag,
                    resolved_model=primary_tag,
                    actual_model="NONE",
                    provider="ollama",
                    device="UNKNOWN",
                    latency_ms=latency_ms,
                    success=False,
                    failure_reason=fail_msg,
                    fallback_used=False,
                    raw_text="",
                    structured_observation=StructuredVisualObservation(),
                    input_image_sha256=image_sha
                )

        # 3. Construct prompt separating task instructions from structured contract
        prompt = self.build_inference_prompt(task_query)

        # 4. Execute inference via Ollama
        device = "UNKNOWN"
        try:
            resp = await self.provider.analyze_image(
                image_bytes=image_bytes,
                prompt=prompt,
                model_name=target_model
            )
            device = await self.detect_running_device(target_model)
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return MultimodalInferenceResult(
                requested_profile=req_profile,
                actual_profile=actual_profile,
                requested_model=primary_tag,
                resolved_model=target_model,
                actual_model=target_model,
                provider="ollama",
                device=device,
                latency_ms=latency_ms,
                success=False,
                failure_reason=f"Inference error: {str(e)}",
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                raw_text="",
                structured_observation=StructuredVisualObservation(),
                input_image_sha256=image_sha
            )

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        if not resp.success or not (resp.text and resp.text.strip()):
            return MultimodalInferenceResult(
                requested_profile=req_profile,
                actual_profile=actual_profile,
                requested_model=primary_tag,
                resolved_model=target_model,
                actual_model=target_model,
                provider="ollama",
                device=device,
                latency_ms=latency_ms,
                success=False,
                failure_reason=resp.error_message or "Empty response from vision model",
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                raw_text=resp.text or "",
                structured_observation=StructuredVisualObservation(),
                input_image_sha256=image_sha
            )

        # 5. Parse structured output strictly
        raw_text = resp.text.strip()
        structured_obs, is_valid_json = self.parse_structured_output(raw_text)

        # 6. Return comprehensive audit result
        return MultimodalInferenceResult(
            requested_profile=req_profile,
            actual_profile=actual_profile,
            requested_model=primary_tag,
            resolved_model=target_model,
            actual_model=target_model,
            provider="ollama",
            device=device,
            latency_ms=latency_ms,
            success=True,
            failure_reason=None if is_valid_json else "MALFORMED_STRUCTURED_OUTPUT",
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            raw_text=raw_text,
            structured_observation=structured_obs,
            input_image_sha256=image_sha
        )


_global_multimodal_router: Optional[MultimodalModelRouter] = None


def get_multimodal_router() -> MultimodalModelRouter:
    """Returns the singleton MultimodalModelRouter instance."""
    global _global_multimodal_router
    if _global_multimodal_router is None:
        _global_multimodal_router = MultimodalModelRouter()
    return _global_multimodal_router
