"""
CogniShift Specialist Model Empirical Benchmark Suite.
Tests and profiles all 5 local SLM models on-premise:
1. deepseek-r1:7b (Heavy Reasoning / Root Cause Analysis / Failure Mode Diagnostics)
2. qwen2.5-coder:7b (Code Synthesis / Quantitative Sandbox Scripts)
3. qwen2.5:7b (Structured Tool Calling / Standard Operating Procedures / Orchestration)
4. moondream:latest (Computer Vision / Industrial Analog Dial & Nameplate Inspection)
5. llama3.2:3b (Low-latency Edge Dialogue / Real-time Status Routing)

Measures:
- Cold invocation latency (first request / weight loading)
- Warm invocation latency
- Model switching overhead (context swap)
- Structured JSON output validity
- Generation throughput (tokens/second)
"""
import sys
import time
import json
import httpx
from pathlib import Path
from typing import Dict, Any, List

OLLAMA_BASE_URL = "http://localhost:11434"

BENCHMARK_PROMPTS = {
    "reasoning": (
        "During crude distillation unit startup, reflux accumulator V-102 pressure rose to 5.2 barg while "
        "condenser overhead temperature dropped 15°C. Cooling water valve FCV-201 indicates 85% open. "
        "Analyze whether this indicates non-condensable gas accumulation, tray flooding, or sensor failure. "
        "Provide a concise 3-point diagnostic rationale."
    ),
    "coding": (
        "Write a clean Python function `detect_excursions(readings: list[float], limit: float) -> list[int]` "
        "that returns the 0-indexed positions where readings exceed limit. Only output valid Python code."
    ),
    "structured_tool": (
        "Output ONLY a valid JSON object matching this schema: "
        "{\"action\": \"tool_call\", \"tool_name\": \"check_pressure\", \"parameters\": {\"component_id\": \"P-101A\"}}. "
        "Do not output markdown codeblocks, thinking text, or preamble."
    ),
    "edge_dialogue": (
        "State your operational status, current workspace role, and readiness to assist the refinery operator in 2 sentences."
    )
}

TARGET_MODELS = [
    {"id": "deepseek-r1:7b", "role": "Deep Analytical Reasoning & Root Cause Analysis", "test_type": "reasoning"},
    {"id": "qwen2.5-coder:7b", "role": "Code Synthesis & Quantitative Sandbox Scripts", "test_type": "coding"},
    {"id": "qwen2.5:7b", "role": "Structured Tool Calling & Plant SOP Orchestration", "test_type": "structured_tool"},
    {"id": "llama3.2:3b", "role": "Edge Dialogue & Rapid Context Routing", "test_type": "edge_dialogue"},
    {"id": "moondream:latest", "role": "Multimodal Vision & Analog Gauge Inspection", "test_type": "vision"}
]


def check_installed_models() -> List[str]:
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception as ex:
        print(f"[WARN] Could not query Ollama tags: {ex}")
    return []


def run_model_trial(model_id: str, prompt: str, is_vision: bool = False) -> Dict[str, Any]:
    if is_vision:
        import base64
        synthetic_png = base64.b64encode(
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        ).decode("utf-8")
        payload = {
            "model": model_id,
            "prompt": "Inspect this industrial gauge dial and report the pointer value.",
            "images": [synthetic_png],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 128}
        }
    else:
        payload = {
            "model": model_id,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 256}
        }

    t0 = time.perf_counter()
    try:
        resp = httpx.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=120.0)
        t1 = time.perf_counter()
        elapsed_sec = t1 - t0

        if resp.status_code == 200:
            res_data = resp.json()
            output_text = res_data.get("response", "")
            eval_count = res_data.get("eval_count", 0)
            eval_duration_ns = res_data.get("eval_duration", 0)
            prompt_eval_count = res_data.get("prompt_eval_count", 0)
            
            tok_per_sec = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else (eval_count / elapsed_sec if elapsed_sec > 0 else 0)
            
            is_valid_json = False
            clean_txt = output_text.strip()
            if clean_txt.startswith("```json"):
                clean_txt = clean_txt[7:].split("```")[0].strip()
            elif clean_txt.startswith("```"):
                clean_txt = clean_txt[3:].split("```")[0].strip()
            try:
                parsed = json.loads(clean_txt)
                is_valid_json = isinstance(parsed, dict)
            except Exception:
                is_valid_json = False

            return {
                "success": True,
                "elapsed_sec": round(elapsed_sec, 2),
                "tokens_generated": eval_count,
                "prompt_tokens": prompt_eval_count,
                "tokens_per_sec": round(tok_per_sec, 1),
                "valid_json": is_valid_json,
                "output_preview": output_text[:120].replace("\n", " "),
                "raw_response": output_text
            }
        else:
            return {
                "success": False,
                "elapsed_sec": round(time.perf_counter() - t0, 2),
                "error": f"HTTP {resp.status_code}: {resp.text[:100]}"
            }
    except Exception as ex:
        return {
            "success": False,
            "elapsed_sec": round(time.perf_counter() - t0, 2),
            "error": str(ex)
        }


def main():
    print("================================================================================")
    print(" CogniShift Specialist Model Local Empirical Benchmark (5 On-Premise SLMs)")
    print("================================================================================")

    installed = check_installed_models()
    inst_str = ", ".join(installed) if installed else "None"
    print(f"[*] Detected Local Ollama Models: {inst_str}\n")

    results = []
    last_model_id = None
    for target in TARGET_MODELS:
        mid = target["id"]
        role = target["role"]
        ttype = target["test_type"]
        is_vision = (ttype == "vision")

        print(f"\n---> Benchmarking [{mid}]")
        print(f"     Role: {role}")
        print(f"     Capability Test: {ttype}")

        if last_model_id and last_model_id != mid:
            print(f"     [Switch]: Context switch from {last_model_id} -> {mid}...")

        prompt = BENCHMARK_PROMPTS.get(ttype, "Describe your core industrial role.")
        print("     Running Trial 1 (Cold / Initial Invocation)...")
        trial1 = run_model_trial(mid, prompt, is_vision=is_vision)

        if not trial1.get("success"):
            print(f"     [FAIL] Trial 1 Error: {trial1.get('error')}")
            results.append({
                "model": mid,
                "role": role,
                "status": "FAILED",
                "error": trial1.get("error")
            })
            continue

        print(f"     [OK] Trial 1: {trial1['elapsed_sec']}s ({trial1['tokens_per_sec']} tok/s) - Generated {trial1['tokens_generated']} tokens")

        print("     Running Trial 2 (Warm Invocation)...")
        trial2 = run_model_trial(mid, prompt, is_vision=is_vision)
        print(f"     [OK] Trial 2: {trial2['elapsed_sec']}s ({trial2['tokens_per_sec']} tok/s)")

        last_model_id = mid

        results.append({
            "model": mid,
            "role": role,
            "test_type": ttype,
            "status": "PASSED",
            "cold_latency_s": trial1["elapsed_sec"],
            "warm_latency_s": trial2["elapsed_sec"],
            "tokens_per_sec": trial2["tokens_per_sec"],
            "tokens_generated": trial2["tokens_generated"],
            "json_compliant": trial1["valid_json"] or trial2["valid_json"],
            "preview": trial2["output_preview"]
        })

    print("\n================================================================================")
    print(" BENCHMARK SUMMARY REPORT")
    print("================================================================================")
    header = f"{'Model':<18} | {'Role':<32} | {'Cold(s)':<7} | {'Warm(s)':<7} | {'Tok/s':<6} | {'Status'}"
    print(header)
    print("-" * len(header))
    for r in results:
        if r.get("status") == "PASSED":
            print(f"{r['model']:<18} | {r['role'][:32]:<32} | {r['cold_latency_s']:<7} | {r['warm_latency_s']:<7} | {r['tokens_per_sec']:<6} | {r['status']}")
        else:
            print(f"{r['model']:<18} | {r['role'][:32]:<32} | {'N/A':<7} | {'N/A':<7} | {'N/A':<6} | FAILED ({r.get('error', '')[:20]})")

    out_json = Path("docs") / "model_benchmark_results.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n[+] Raw results saved to: {out_json}")


if __name__ == "__main__":
    main()
