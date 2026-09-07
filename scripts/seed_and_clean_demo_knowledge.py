"""Deduplicate Knowledge Sources and Ingest Missing Demo Datasets for Workspace 1.

Cleans duplicate records and ingests:
- equipment_readings.csv
- MRPL_SAP_PM_Maintenance_Work_Orders.csv
- MRPL_3Year_Financial_and_Operational_Audit.xlsx
- MRPL_Unit01_SCADA_Continuous_Telemetry_48H.xlsx
into SQLite and ChromaDB, then associates all source IDs with Agent 1.
"""
import os
import sys
import json
import shutil
import hashlib
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from cognishift.app.config import settings
from cognishift.core.retriever import chroma_client, embedding_model

DB_PATH = settings.database_path
DEMO_DIR = ROOT_DIR / "data" / "demo"
WS1_UPLOADS = ROOT_DIR / "data" / "workspaces" / "1" / "uploads"
WS1_DOCS = ROOT_DIR / "data" / "workspaces" / "1" / "documents"
WS1_UPLOADS.mkdir(parents=True, exist_ok=True)
WS1_DOCS.mkdir(parents=True, exist_ok=True)


def deduplicate_knowledge_sources():
    """Remove duplicate rows for the same document name in Workspace 1."""
    print("--- 1. Deduplicating Workspace 1 Knowledge Sources ---")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT name, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
        FROM knowledge_sources
        WHERE workspace_id = 1
        GROUP BY name
        HAVING cnt > 1
    """)
    dup_rows = c.fetchall()
    
    for row in dup_rows:
        name = row["name"]
        id_list = [int(x) for x in row["ids"].split(",")]
        keep_id = max(id_list)
        remove_ids = [x for x in id_list if x != keep_id]
        print(f"  Document '{name}': keeping ID #{keep_id}, removing duplicate IDs: {remove_ids}")

        placeholders = ",".join("?" for _ in remove_ids)
        c.execute(f"DELETE FROM document_pages WHERE source_id IN ({placeholders})", remove_ids)
        c.execute(f"DELETE FROM document_processing_jobs WHERE source_id IN ({placeholders})", remove_ids)
        c.execute(f"DELETE FROM knowledge_sources WHERE id IN ({placeholders})", remove_ids)

        try:
            collection = chroma_client.get_or_create_collection(name="workspace_1")
            for rid in remove_ids:
                collection.delete(where={"source_id": rid})
        except Exception as ex:
            print(f"  Warning: ChromaDB cleanup for source #{remove_ids}: {ex}")

    conn.commit()
    conn.close()
    print("  [OK] Deduplication complete.")


def ingest_demo_files():
    """Ingest the 4 missing demo files into SQLite and ChromaDB."""
    print("--- 2. Ingesting Missing Demo Datasets into Workspace 1 ---")
    import pandas as pd
    import openpyxl

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    collection = chroma_client.get_or_create_collection(name="workspace_1")

    files_to_ingest = [
        ("equipment_readings.csv", "spreadsheet"),
        ("MRPL_SAP_PM_Maintenance_Work_Orders.csv", "spreadsheet"),
        ("MRPL_3Year_Financial_and_Operational_Audit.xlsx", "spreadsheet"),
        ("MRPL_Unit01_SCADA_Continuous_Telemetry_48H.xlsx", "spreadsheet"),
    ]

    for fname, stype in files_to_ingest:
        src_path = DEMO_DIR / fname
        if not src_path.exists():
            print(f"  [SKIP] {fname} not found in {DEMO_DIR}")
            continue

        # Check if already exists in workspace 1
        c.execute("SELECT id FROM knowledge_sources WHERE workspace_id = 1 AND name = ?", (fname,))
        existing = c.fetchone()
        if existing:
            old_id = existing["id"]
            c.execute("DELETE FROM document_pages WHERE source_id = ?", (old_id,))
            c.execute("DELETE FROM document_processing_jobs WHERE source_id = ?", (old_id,))
            c.execute("DELETE FROM knowledge_sources WHERE id = ?", (old_id,))
            try:
                collection.delete(where={"source_id": old_id})
            except Exception:
                pass
            conn.commit()

        # Copy to uploads and documents
        dest_upload = WS1_UPLOADS / fname
        dest_doc = WS1_DOCS / fname
        shutil.copy2(src_path, dest_upload)
        shutil.copy2(src_path, dest_doc)

        with open(src_path, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        # Insert knowledge_source record
        c.execute("""
            INSERT INTO knowledge_sources 
            (workspace_id, name, source_type, original_filename, local_path, processing_status, checksum) 
            VALUES (1, ?, ?, ?, ?, 'processing', ?)
        """, (fname, stype, fname, str(dest_upload), checksum))
        conn.commit()
        source_id = c.lastrowid
        print(f"  Ingesting '{fname}' as source #{source_id}...")

        chunks = []
        metadatas = []
        ids = []

        ext = Path(fname).suffix.lower()
        if ext == ".csv":
            try:
                df = pd.read_csv(src_path)
                # Statistical summary chunk
                summary_lines = [
                    f"### Dataset Overview: {fname}",
                    f"Total Rows: {len(df)}, Total Columns: {len(df.columns)}",
                    f"Columns: {', '.join(df.columns)}",
                    "\n### Statistical Summary:\n" + df.describe(include='all').to_string(),
                    "\n### First 10 Rows Preview:\n" + df.head(10).to_string(index=False)
                ]
                summary_text = "\n".join(summary_lines)
                chunks.append(summary_text)
                metadatas.append({
                    "workspace_id": 1,
                    "source_id": source_id,
                    "document": fname,
                    "page_number": 1,
                    "chunk_index": 0
                })
                ids.append(f"ws1_src_{source_id}_summary")

                # Insert into document_pages
                c.execute("""
                    INSERT INTO document_pages (source_id, workspace_id, processing_version, page_number, text_content, extraction_method)
                    VALUES (?, 1, 'v1', 1, ?, 'pandas_csv')
                """, (source_id, summary_text))

                # Also create row batch chunks for fine-grained retrieval
                batch_size = 40
                for b_idx, start_row in enumerate(range(0, min(len(df), 200), batch_size)):
                    batch_df = df.iloc[start_row:start_row + batch_size]
                    batch_text = f"### {fname} (Rows {start_row + 1} to {start_row + len(batch_df)}):\n" + batch_df.to_string(index=False)
                    chunks.append(batch_text)
                    metadatas.append({
                        "workspace_id": 1,
                        "source_id": source_id,
                        "document": fname,
                        "page_number": 1,
                        "chunk_index": b_idx + 1
                    })
                    ids.append(f"ws1_src_{source_id}_batch_{b_idx}")

            except Exception as e:
                print(f"  Error parsing CSV {fname}: {e}")

        elif ext == ".xlsx":
            try:
                wb = openpyxl.load_workbook(src_path, data_only=True)
                for sheet_idx, sname in enumerate(wb.sheetnames):
                    ws = wb[sname]
                    rows_data = []
                    for r in ws.iter_rows(max_row=60, max_col=15, values_only=True):
                        if any(cell is not None for cell in r):
                            rows_data.append(" | ".join(str(c) if c is not None else "" for c in r))
                    
                    if rows_data:
                        page_num = sheet_idx + 1
                        sheet_text = f"### Workbook: {fname} | Sheet: {sname} (Page {page_num})\n" + "\n".join(rows_data)
                        chunks.append(sheet_text)
                        metadatas.append({
                            "workspace_id": 1,
                            "source_id": source_id,
                            "document": fname,
                            "sheet_name": sname,
                            "page_number": page_num,
                            "chunk_index": 0
                        })
                        ids.append(f"ws1_src_{source_id}_sheet_{sheet_idx}")

                        c.execute("""
                            INSERT INTO document_pages (source_id, workspace_id, processing_version, page_number, text_content, extraction_method)
                            VALUES (?, 1, 'v1', ?, ?, 'openpyxl_sheet')
                        """, (source_id, page_num, sheet_text))
            except Exception as e:
                print(f"  Error parsing XLSX {fname}: {e}")

        # Generate embeddings and upsert into ChromaDB
        if chunks:
            embs = list(embedding_model.embed(chunks))
            emb_lists = [e.tolist() for e in embs]
            collection.upsert(ids=ids, embeddings=emb_lists, metadatas=metadatas, documents=chunks)
            print(f"  [OK] Indexed {len(chunks)} chunks into ChromaDB for '{fname}'.")

        # Mark source completed
        c.execute("""
            UPDATE knowledge_sources 
            SET processing_status = 'completed', chunk_count = ?
            WHERE id = ?
        """, (len(chunks), source_id))
        conn.commit()

    conn.close()
    print("  [OK] Ingestion complete.")


def update_agent_sources():
    """Ensure Agent 1 (Refinery Maintenance Specialist) has access to all Workspace 1 knowledge sources."""
    print("--- 3. Updating Agent 1 Knowledge Source IDs ---")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT id, name FROM knowledge_sources WHERE workspace_id = 1 AND processing_status = 'completed'")
    sources = c.fetchall()
    all_source_ids = [r["id"] for r in sources]
    sources_json = json.dumps(all_source_ids)

    c.execute("""
        UPDATE agent_definitions 
        SET knowledge_source_ids = ?
        WHERE workspace_id = 1
    """, (sources_json,))
    conn.commit()
    conn.close()
    print(f"  [OK] Associated {len(all_source_ids)} knowledge sources with Workspace 1 agents: {all_source_ids}")


def main():
    print("============================================================")
    print("  CLEANING & SEEDING DEMO KNOWLEDGE IN COGNISHIFT")
    print("============================================================")
    deduplicate_knowledge_sources()
    ingest_demo_files()
    update_agent_sources()
    print("============================================================")
    print("  KNOWLEDGE REPAIR & SEED COMPLETE")
    print("============================================================")


if __name__ == "__main__":
    main()
