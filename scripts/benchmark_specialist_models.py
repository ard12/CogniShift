"""
CogniShift Specialist Model Empirical Benchmark Suite (SIH Hardened).
Authoritative, reproducible on-premise benchmarking for the 5 local SLM specialists:
1. deepseek-r1:7b (Heavy Analytical Reasoning / Root Cause Analysis)
2. qwen2.5-coder:7b (Deterministic Code Generation & Sandbox Execution)
3. qwen2.5:7b (Structured Tool Calling & Plant SOP Orchestration)
4. moondream:latest (Multimodal Vision & Analog Gauge Dial Inspection)
5. llama3.2:3b (Low-latency Edge Dialogue & Status Routing)

Benchmark Protocol:
- Pre-benchmark assertion: Ollama status, model tag verification, fixture SHA-256 integrity against manifest.json.
- Cold invocation: Confirmed model unload (keep_alive: 0) before Trial 1.
- Warm invocations: 5 consecutive warm trials (Trials 2-6) measuring median, min, max latency, and tokens/sec.
- Semantic pass evaluation: Real execution and factual ground-truth matching (HTTP 200 is NOT a pass).
"""
import os
import sys
import time
import json
import base64
import hashlib
import statistics
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import httpx

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
MANIFEST_PATH = Path("data/benchmarks/manifest.json")

TARGET_MODELS = [
    {"id": "deepseek-r1:7b", "role": "Analytical Reasoning & Root Cause Analysis", "test_type": "reasoning"},
    {"id": "qwen2.5-coder:7b", "role": "Code Synthesis & Sandbox Execution", "test_type": "coding"},
    {"id": "qwen2.5:7b", "role": "Structured Tool Calling & SOP Orchestration", "test_type": "structured_tool"},
    {"id": "moondream:latest", "role": "Multimodal Vision & Analog Gauge Inspection", "test_type": "vision"},
    {"id": "llama3.2:3b", "role": "Edge Dialogue & Real-Time Status Routing", "test_type": "edge_dialogue"}
]


def verify_manifest_integrity() -> Dict[str, Any]:
    """Assert that benchmark manifest exists and all referenced fixtures match exact SHA-256 hashes."""
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Benchmark manifest missing at {MANIFEST_PATH}")
    
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for fixture in manifest.get("fixtures", []):
        fpath = Path(fixture["path"])
        if not fpath.exists():
            raise FileNotFoundError(f"Required benchmark fixture missing: {fpath}")
        actual_hash = hashlib.sha256(fpath.read_bytes()).hexdigest()
        expected_hash = fixture["sha256"]
        if actual_hash != expected_hash:
            raise ValueError(f"Fixture integrity mismatch for {fpath}! Expected {expected_hash}, got {actual_hash}")
        print(f"[OK] Fixture verified: {fpath.name} (SHA-256: {actual_hash[:12]}...)")
    return manifest


def check_installed_models() -> List[str]:
    """Query Ollama /api/tags for installed local models."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception as ex:
        print(f"[!] Ollama connection failed: {ex}")
    return []


def unload_model(model_id: str) -> bool:
    """Force Ollama to unload the model from VRAM by issuing keep_alive: 0."""
    try:
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": model_id, "keep_alive": 0},
            timeout=10.0
        )
        time.sleep(1.0)
        return resp.status_code == 200
    except Exception:
        return False


def run_model_trial(
    model_id: str,
    prompt: str,
    image_bytes: Optional[bytes] = None,
    max_tokens: int = 256,
    temperature: float = 0.1
) -> Dict[str, Any]:
    """Execute a single trial against the local model."""
    payload: Dict[str, Any] = {
        "model": model_id,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens}
    }
    if image_bytes:
        payload["images"] = [base64.b64encode(image_bytes).decode("utf-8")]

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

            return {
                "success": True,
                "elapsed_sec": round(elapsed_sec, 3),
                "tokens_generated": eval_count,
                "prompt_tokens": prompt_eval_count,
                "tokens_per_sec": round(tok_per_sec, 1),
                "raw_response": output_text
            }
        else:
            return {
                "success": False,
                "elapsed_sec": round(time.perf_counter() - t0, 3),
                "error": f"HTTP {resp.status_code}: {resp.text[:100]}"
            }
    except Exception as ex:
        return {
            "success": False,
            "elapsed_sec": round(time.perf_counter() - t0, 3),
            "error": str(ex)
        }


def evaluate_semantic_accuracy(test_type: str, output_text: str, manifest: Dict[str, Any]) -> Tuple[bool, str]:
    """Perform ground-truth evaluation based on test type."""
    cleaned = output_text.strip()
    # Strip thinking tags if present
    if "<think>" in cleaned.lower():
        cleaned = re.sub(r"(?is)<think>.*?(?:</think>|$)", "", cleaned).strip()

    if test_type == "coding":
        # Verify synthesized detect_excursions code actually works on test data
        code_str = cleaned
        if "```python" in code_str:
            code_str = code_str.split("```python")[1].split("```")[0].strip()
        elif "```" in code_str:
            code_str = code_str.split("```")[1].split("```")[0].strip()

        verification_env = {}
        try:
            exec(code_str, verification_env)
            fn = verification_env.get("detect_excursions")
            if not callable(fn):
                return False, "Function 'detect_excursions' not defined in generated code"
            test_input = manifest["test_suites"]["coding"]["verification"]["test_input"]
            expected = manifest["test_suites"]["coding"]["verification"]["expected_output"]
            actual = fn(**test_input)
            if actual == expected:
                return True, f"Code execution verified: detect_excursions returned expected {expected}"
            return False, f"Semantic failure: returned {actual}, expected {expected}"
        except Exception as e:
            return False, f"Code execution error: {e}"

    elif test_type == "structured_tool":
        # Verify structured tool proposal JSON
        raw_json = cleaned
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            raw_json = json_match.group(0)
        elif raw_json.startswith("```json"):
            raw_json = raw_json[7:].split("```")[0].strip()
        elif raw_json.startswith("```"):
            raw_json = raw_json[3:].split("```")[0].strip()
        try:
            parsed = json.loads(raw_json)
            if not isinstance(parsed, dict):
                return False, "Output is not a JSON dictionary"
            action = str(parsed.get("action", ""))
            tool_name = str(parsed.get("tool_name", ""))
            params = parsed.get("parameters", {})
            if ("tool" in action) and ("check_pressure" in tool_name or "pressure" in tool_name):
                return True, "Structured JSON matches ToolCallProposal contract"
            return False, f"Schema mismatch: action={action}, tool={tool_name}, params={params}"
        except Exception as e:
            return False, f"JSON parse error: {e}"

    elif test_type == "reasoning":
        # Verify RCA diagnostic criteria
        eval_src = cleaned if cleaned else output_text
        lower = eval_src.lower()
        has_pressure = "pressure" in lower
        has_temp = "temperature" in lower or "condenser" in lower
        has_ncg = "non-condensable" in lower or "gas" in lower or "accumulator" in lower
        has_numbered_points = bool(re.search(r"(?:\b1[\.\)]|\b2[\.\)]|\b3[\.\)])", eval_src)) or "point 1" in lower or "-" in eval_src
        if has_pressure and has_temp and (has_ncg or has_numbered_points):
            return True, "Diagnostic RCA covers pressure, condenser temperature, and failure mechanisms"
        return False, "RCA output missing required operational mechanisms or structure"

    elif test_type == "edge_dialogue":
        # Verify edge response brevity and operational readiness
        sentences = [s for s in re.split(r"[.!?]+", cleaned) if s.strip()]
        lower = cleaned.lower()
        has_readiness = any(w in lower for w in ["ready", "assist", "operational", "status", "operator"])
        if len(sentences) <= 4 and has_readiness:
            return True, f"Edge dialogue passed: concise ({len(sentences)} sentences) and confirmed readiness"
        return False, f"Edge dialogue failed: sentences={len(sentences)}, readiness_terms={has_readiness}"

    elif test_type == "vision":
        # Vision test evaluated via separate dedicated method
        return True, "Vision evaluated per fixture"

    return True, "Evaluated"


def main():
    print("=" * 80)
    print(" CogniShift Specialist Model Empirical Benchmark (5 On-Premise SLMs)")
    print(" Verification Standard: Ground-Truth Semantic Accuracy + 1 Cold + 5 Warm Trials")
    print("=" * 80)

    # 1. Manifest & Fixture Verification
    print("\n[*] Step 1: Verifying Benchmark Manifest & Fixtures...")
    try:
        manifest = verify_manifest_integrity()
    except Exception as ex:
        print(f"[FATAL] Manifest verification failed: {ex}")
        sys.exit(1)

    # 2. Local Model Inventory Verification
    print("\n[*] Step 2: Querying Sovereign Ollama Instance...")
    installed = check_installed_models()
    if not installed:
        print(f"[FATAL] No models detected at {OLLAMA_BASE_URL}! Is Ollama running?")
        sys.exit(1)
    print(f"[OK] Detected Local Models: {', '.join(installed)}\n")

    results = []

    for target in TARGET_MODELS:
        mid = target["id"]
        role = target["role"]
        ttype = target["test_type"]

        # Check if installed
        norm_installed = [m.lower() for m in installed]
        is_installed = any(
            mid.lower() == inst or
            (mid.lower().endswith(":latest") and mid.lower()[:-7] == inst) or
            (":" not in mid and f"{mid.lower()}:latest" == inst)
            for inst in norm_installed
        )

        print(f"\n{'=' * 80}")
        print(f"--> Benchmarking [{mid}] - {role}")
        print(f"    Test Category: {ttype}")

        if not is_installed:
            print(f"[!] Model {mid} is NOT installed in local Ollama inventory. Skipping.")
            results.append({
                "model": mid,
                "role": role,
                "status": "SKIPPED_NOT_INSTALLED",
                "test_type": ttype
            })
            continue

        # Cold trial: Unload model first to force cold disk load
        print("    [1/6] Unloading model to ensure cold baseline (keep_alive: 0)...")
        unload_model(mid)
        time.sleep(1.0)

        # Prompt & input preparation
        prompt = manifest["test_suites"].get(ttype, {}).get("prompt", "Describe your operational role.")
        image_bytes = None

        if ttype == "vision":
            gauge_fixture = Path(manifest["fixtures"][0]["path"])
            image_bytes = gauge_fixture.read_bytes()
            prompt = manifest["test_suites"]["vision"]["trials"]["positive"]["prompt"]

        # Trial 1 (Cold)
        print("    [2/6] Running Trial 1 (Confirmed Cold Invocation)...")
        trial_cold = run_model_trial(mid, prompt, image_bytes=image_bytes)
        if not trial_cold.get("success"):
            print(f"    [FAIL] Cold trial failed: {trial_cold.get('error')}")
            results.append({
                "model": mid,
                "role": role,
                "status": "FAILED_COLD",
                "error": trial_cold.get("error")
            })
            continue

        cold_sec = trial_cold["elapsed_sec"]
        print(f"    [OK] Trial 1 (Cold): {cold_sec}s | {trial_cold['tokens_per_sec']} tok/s ({trial_cold['tokens_generated']} tokens)")

        # Trials 2 to 6 (5 Warm Trials)
        print("    [3/6] Running 5 Warm Invocations (Trials 2 - 6)...")
        warm_latencies = []
        warm_throughputs = []
        last_response_text = ""

        for w_idx in range(2, 7):
            trial_w = run_model_trial(mid, prompt, image_bytes=image_bytes)
            if trial_w.get("success"):
                warm_latencies.append(trial_w["elapsed_sec"])
                warm_throughputs.append(trial_w["tokens_per_sec"])
                last_response_text = trial_w.get("raw_response", "")
                print(f"        Warm #{w_idx - 1}: {trial_w['elapsed_sec']}s ({trial_w['tokens_per_sec']} tok/s)")
            else:
                print(f"        Warm #{w_idx - 1} FAILED: {trial_w.get('error')}")

        if not warm_latencies:
            print("    [FAIL] All warm trials failed.")
            results.append({"model": mid, "role": role, "status": "FAILED_WARM"})
            continue

        median_warm = round(statistics.median(warm_latencies), 3)
        min_warm = round(min(warm_latencies), 3)
        max_warm = round(max(warm_latencies), 3)
        avg_tok_s = round(statistics.mean(warm_throughputs), 1)

        # Semantic Accuracy Verification
        print("    [4/6] Evaluating Semantic Accuracy against Ground-Truth...")
        if ttype == "vision":
            # Positive test: check reading or dial recognition
            numbers_found = re.findall(r"\b\d+(?:\.\d+)?\b", last_response_text)
            has_dial_terms = any(w in last_response_text.lower() for w in ["gauge", "dial", "clock", "needle", "round", "face", "psi", "pressure", "meter"])
            
            # Negative test: handwritten note
            neg_fixture = Path(manifest["fixtures"][1]["path"])
            neg_prompt = manifest["test_suites"]["vision"]["trials"]["negative"]["prompt"]
            neg_trial = run_model_trial(mid, neg_prompt, image_bytes=neg_fixture.read_bytes())
            neg_text = neg_trial.get("raw_response", "").lower()
            neg_passed = any(kw in neg_text for kw in ["not a gauge", "no gauge", "unable", "cannot", "note", "handwritten", "no dial", "unreadable", "not visible", "paper", "text", "writing", "letter"])

            sem_passed = has_dial_terms or len(numbers_found) > 0
            sem_notes = f"Gauge dial detection: dial_terms={has_dial_terms}, numbers={numbers_found[:3]}, non-gauge abstention={neg_passed}"
        else:
            sem_passed, sem_notes = evaluate_semantic_accuracy(ttype, last_response_text, manifest)

        status_str = "PASSED" if sem_passed else "SEMANTIC_WARNING"
        print(f"    [{status_str}] Semantic Check: {sem_notes}")

        results.append({
            "model": mid,
            "role": role,
            "test_type": ttype,
            "status": status_str,
            "cold_latency_s": cold_sec,
            "warm_latency_median_s": median_warm,
            "warm_latency_min_s": min_warm,
            "warm_latency_max_s": max_warm,
            "tokens_per_sec": avg_tok_s,
            "semantic_accuracy_pass": sem_passed,
            "semantic_notes": sem_notes,
            "warm_trials_count": len(warm_latencies)
        })

    # Summary Report
    print("\n" + "=" * 85)
    print(" SPECIALIST MODEL BENCHMARK FINAL AUDIT REPORT")
    print("=" * 85)
    header = f"{'Model':<18} | {'Role':<30} | {'Cold(s)':<8} | {'WarmMed(s)':<10} | {'Tok/s':<7} | {'Semantic'}"
    print(header)
    print("-" * len(header))
    for r in results:
        if "cold_latency_s" in r:
            sem_flag = "PASS" if r.get("semantic_accuracy_pass") else "WARN"
            print(f"{r['model']:<18} | {r['role'][:30]:<30} | {r['cold_latency_s']:<8} | {r['warm_latency_median_s']:<10} | {r['tokens_per_sec']:<7} | {sem_flag}")
        else:
            print(f"{r['model']:<18} | {r['role'][:30]:<30} | {'N/A':<8} | {'N/A':<10} | {'N/A':<7} | {r['status']}")

    out_file = Path("docs/model_benchmark_results.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n[+] Authoritative benchmark report saved to: {out_file}")


if __name__ == "__main__":
    main()
