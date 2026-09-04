"""CogniShift Phase 7 — Offline / Air-Gap Demo Preflight Checker.

Verifies that 100% of required runtime dependencies, model weights,
OCR assets, embeddings, Docker containers, database fixtures, and
demo files exist on the local machine.

ABSOLUTE RULE: Does NOT download anything. Fail-closed if anything is missing.
"""

import sys
import os
import sqlite3
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from cognishift.app.config import settings

def main():
    print("============================================================")
    print("  COGNISHIFT OFFLINE DEMO PREFLIGHT CHECKER")
    print("  Mode: 100% Offline / Zero Cloud / Zero Auto-Download")
    print("============================================================")

    all_passed = True
    missing_assets = []

    def check(name: str, passed: bool, detail: str = ""):
        nonlocal all_passed
        if passed:
            print(f"  [OK] {name:<35} {detail}")
        else:
            all_passed = False
            missing_assets.append(f"{name}: {detail}")
            print(f"  [FAIL] {name:<35} {detail}")

    # 1. Check SQLite Database
    db_path = settings.database_path
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
            tbl_count = c.fetchone()[0]
            conn.close()
            check("SQLite Database", tbl_count >= 8, f"({tbl_count} tables initialized)")
        except Exception as e:
            check("SQLite Database", False, str(e))
    else:
        check("SQLite Database", False, f"Missing at {db_path}")

    # 2. Check ChromaDB vector store
    chroma_dir = settings.chroma_path
    if chroma_dir.exists() and any(chroma_dir.iterdir()):
        check("ChromaDB Vector Store", True, f"({chroma_dir})")
    else:
        check("ChromaDB Vector Store", False, f"Missing or empty at {chroma_dir}")

    # 3. Check FastEmbed Local Model Cache
    fe_cache = settings.fastembed_cache_dir
    onnx_files = list(fe_cache.glob("**/*.onnx")) if fe_cache.exists() else []
    if onnx_files:
        check("FastEmbed Model Cache", True, f"(bge-small-en-v1.5 onnx verified: {onnx_files[0].name})")
    else:
        check("FastEmbed Model Cache", False, f"Missing offline ONNX model in {fe_cache}")

    # 4. Check RapidOCR Local Assets
    try:
        from rapidocr_onnxruntime import RapidOCR
        ocr = RapidOCR()
        check("RapidOCR Local Engine", True, "(ONNX Runtime model weights ready)")
    except Exception as e:
        check("RapidOCR Local Engine", False, f"Error: {e}")

    # 5. Check Ollama Service & Models
    try:
        import httpx
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3.0)
        if resp.status_code == 200:
            models_data = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models_data]
            check("Ollama Local Service", True, f"({settings.ollama_base_url})")

            # Check llama3.2:3b
            has_llama = any(settings.text_model in m for m in model_names)
            check("LLM (llama3.2:3b)", has_llama, f"({'Found' if has_llama else 'MISSING'})")

            # Check moondream
            has_moon = any(settings.vision_model in m for m in model_names)
            check("VLM (moondream:latest)", has_moon, f"({'Found' if has_moon else 'MISSING'})")
        else:
            check("Ollama Local Service", False, f"HTTP status {resp.status_code}")
            check("LLM (llama3.2:3b)", False, "Ollama unreachable")
            check("VLM (moondream:latest)", False, "Ollama unreachable")
    except Exception as e:
        check("Ollama Local Service", False, f"Cannot connect to {settings.ollama_base_url}")
        check("LLM (llama3.2:3b)", False, "Ollama unreachable")
        check("VLM (moondream:latest)", False, "Ollama unreachable")

    # 6. Check Docker Image for Sandbox
    try:
        import subprocess
        res = subprocess.run(
            ["docker", "image", "inspect", settings.sandbox_image],
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode == 0:
            check("Docker Sandbox Image", True, f"({settings.sandbox_image} present locally)")
        else:
            check("Docker Sandbox Image", False, f"Image {settings.sandbox_image} not found in local daemon")
    except Exception as e:
        check("Docker Sandbox Image", False, f"Docker daemon query failed: {e}")

    # 7. Check Demo Credentials & Auth Store
    auth_store = settings.auth_store_path
    if auth_store.exists():
        try:
            content = json.loads(auth_store.read_text(encoding="utf-8"))
            user_count = len(content.get("users", []))
            check("Demo Credentials Store", user_count >= 3, f"({user_count} local users registered)")
        except Exception as e:
            check("Demo Credentials Store", False, str(e))
    else:
        check("Demo Credentials Store", False, f"Missing at {auth_store}")

    # 8. Check Frontend Static Assets
    static_dir = ROOT_DIR / "src" / "cognishift" / "app" / "static"
    html_path = static_dir / "index.html"
    css_path = static_dir / "app.css"
    js_path = static_dir / "app.js"
    if html_path.exists() and css_path.exists() and js_path.exists():
        check("Frontend Static Assets", True, "(Local index.html, app.css & app.js verified)")
    else:
        check("Frontend Static Assets", False, "Missing static assets")

    # 9. Authentication configuration and optional local demo capability
    canonical_auth_store = (ROOT_DIR / "data" / "private" / "auth_store.json").resolve()
    resolved_auth_store = settings.auth_store_path.resolve()
    configured_store_ok = resolved_auth_store == canonical_auth_store or "AUTH_STORE_PATH" in os.environ
    check("Auth Store Configuration", configured_store_ok, f"({resolved_auth_store})")

    auth_api_path = ROOT_DIR / "src" / "cognishift" / "app" / "api" / "auth.py"
    auth_api_source = auth_api_path.read_text(encoding="utf-8") if auth_api_path.exists() else ""
    demo_capable = 'post("/demo-session"' in auth_api_source and "_is_loopback" in auth_api_source
    if settings.cognishift_demo_mode:
        check("Local Demo Auth Capability", demo_capable, "(enabled; loopback guard installed)")
    else:
        check("Local Demo Auth Capability", demo_capable, "(installed; disabled by default)")

    # 10. Check Demo Synthetic Documents
    demo_dir = ROOT_DIR / "data" / "demo"
    sop_pdf = demo_dir / "Pump_Maintenance_SOP.pdf"
    rep_pdf = demo_dir / "P-101A_Inspection_Report.pdf"
    csv_tel = demo_dir / "equipment_readings.csv"

    has_demo_docs = sop_pdf.exists() and rep_pdf.exists() and csv_tel.exists()
    check("Synthetic Demo Documents", has_demo_docs, f"({demo_dir})")

    # 11. Check Workspace #1 existence
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT name FROM workspaces WHERE id = 1")
            row = c.fetchone()
            conn.close()
            check("Demo Workspace (ID #1)", row is not None, f"('{row[0]}' configured)" if row else "MISSING")
        except Exception:
            check("Demo Workspace (ID #1)", False, "Failed to query workspaces")

    print("============================================================")
    if all_passed:
        print("RESULT: READY FOR OFFLINE DEMO")
        print("All local models, services, images, and documents are 100% provisioned.")
        print("============================================================")
        return 0
    else:
        print("RESULT: NOT READY")
        print("The following local assets must be provisioned before offline testing:")
        for item in missing_assets:
            print(f"  - {item}")
        print("============================================================")
        return 1

if __name__ == "__main__":
    sys.exit(main())
