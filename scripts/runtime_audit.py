"""Runtime audit script to inspect SQLite tables, ChromaDB collections, and Ollama service."""

import sqlite3
import json
import urllib.request
from pathlib import Path
import chromadb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "cognishift.db"
CHROMA_PATH = PROJECT_ROOT / "data" / "chroma"

def audit_sqlite():
    print("=== 1. SQLITE DATABASE AUDIT (data/cognishift.db) ===")
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} does not exist!")
        return {}
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    tables = [
        "workspaces",
        "agent_definitions",
        "knowledge_sources",
        "tool_definitions",
        "agent_runs",
        "run_events",
        "approval_requests",
        "audit_events",
        "graph_nodes",
        "graph_edges",
    ]
    
    table_counts = {}
    table_samples = {}
    
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            cnt = cursor.fetchone()["cnt"]
            table_counts[table] = cnt
            
            cursor.execute(f"SELECT * FROM {table} LIMIT 2")
            rows = [dict(r) for r in cursor.fetchall()]
            table_samples[table] = rows
            print(f"Table: {table:<22} | Row Count: {cnt:>5}")
        except Exception as e:
            table_counts[table] = f"Error: {e}"
            print(f"Table: {table:<22} | Error: {e}")
            
    conn.close()
    return {"counts": table_counts, "samples": table_samples}

def audit_chroma():
    print("\n=== 2. CHROMADB AUDIT (data/chroma) ===")
    if not CHROMA_PATH.exists():
        print(f"ERROR: {CHROMA_PATH} does not exist!")
        return {}
        
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collections = client.list_collections()
    print(f"Total Collections: {len(collections)}")
    
    col_details = []
    for col in collections:
        count = col.count()
        print(f"Collection: {col.name:<25} | Documents/Embeddings Count: {count:>5}")
        sample = col.peek(limit=2)
        col_details.append({
            "name": col.name,
            "count": count,
            "metadata": col.metadata,
            "sample_ids": sample.get("ids", []) if sample else []
        })
    return {"collections": col_details}

def audit_ollama():
    print("\n=== 3. OLLAMA SERVICE AUDIT (http://localhost:11434/api/tags) ===")
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", headers={"User-Agent": "AuditScript/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("models", [])
            print(f"Ollama Status: ONLINE | Total Models: {len(models)}")
            
            model_info = []
            for m in models:
                name = m.get("name")
                size_gb = round(m.get("size", 0) / (1024**3), 2)
                details = m.get("details", {})
                param_size = details.get("parameter_size", "N/A")
                quant_level = details.get("quantization_level", "N/A")
                family = details.get("family", "N/A")
                fmt = details.get("format", "N/A")
                modified = m.get("modified_at", "N/A")
                
                print(f"- Model: {name:<22} | Size: {size_gb:>5.2f} GB | Params: {param_size:<6} | Quant: {quant_level:<8} | Family: {family}")
                model_info.append({
                    "name": name,
                    "size_gb": size_gb,
                    "parameter_size": param_size,
                    "quantization_level": quant_level,
                    "family": family,
                    "format": fmt,
                    "modified_at": modified
                })
            return {"status": "online", "models": model_info}
    except Exception as e:
        print(f"Ollama Status: OFFLINE or Error: {e}")
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    sqlite_res = audit_sqlite()
    chroma_res = audit_chroma()
    ollama_res = audit_ollama()
