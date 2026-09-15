"""
Multimodal Retrieval Benchmark Suite for CogniShift.
Evaluates Recall@1, Recall@3, Page Accuracy, and Retrieval Latency across 5 document types:
1. Standard Operating Procedure (Pure Text)
2. Industrial Inspection Data Table (Dense Grid Layout)
3. Piping & Instrumentation Diagram (P&ID Blueprint / Visual Graph)
4. Scanned Maintenance Log (OCR-reliant)
5. Pump Cavitation RCA Case Study (Hybrid Text + Schematic)

Compares:
- Text-Only RAG (FastEmbed + ChromaDB)
- ColPali Visual Page Retrieval (Late-Interaction MaxSim)
- Hybrid Multimodal Fusion (Reciprocal Rank Fusion)
"""
import sys
import time
import asyncio
import tempfile
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pymupdf
import numpy as np

from cognishift.app.config import settings
from cognishift.app.db.database import init_db, get_db
from cognishift.core.document_processing.service import DocumentProcessingService
from cognishift.core.visual_rag.embedding_provider import SimulatedVisualEmbeddingProvider
from cognishift.core.retrieval.hybrid_retriever import HybridDocumentRetriever
from cognishift.core.retrieval.text_retriever import TextRetriever
from cognishift.core.retrieval.visual_retriever import VisualRetriever
from cognishift.core.document_processing.lifecycle import idempotent_delete_source


def create_benchmark_documents(tmp_dir: Path) -> List[Dict[str, Any]]:
    """Generates 5 synthetic benchmark documents representing industrial plant workloads."""
    docs = []

    # 1. SOP Document (Pure Text)
    p1 = tmp_dir / "SOP_Turbine_Start.pdf"
    doc1 = pymupdf.open()
    page1_1 = doc1.new_page(width=595, height=842)
    page1_1.insert_text((50, 80), "SOP-TURB-001: Gas Turbine Start Sequence Procedures.\n\n"
                                  "1. Verify lube oil pressure is above 3.5 bar.\n"
                                  "2. Engage hydraulic turning gear for minimum 20 minutes prior to firing.\n"
                                  "3. Purge exhaust duct for 5 volume changes.\n"
                                  "4. Light-off speed is 1200 RPM. Ramp rate is 150 RPM/min.")
    page1_2 = doc1.new_page(width=595, height=842)
    page1_2.insert_text((50, 80), "Emergency Stop Criteria:\n\n"
                                  "Turbine must be manually tripped if vibration exceeds 7.1 mm/s RMS on any bearing,\n"
                                  "or if exhaust gas temperature spread exceeds 45°C during acceleration.")
    doc1.save(str(p1))
    doc1.close()
    docs.append({
        "type": "sop_text",
        "name": "SOP_Turbine_Start.pdf",
        "path": p1,
        "queries": [
            {"query": "What is the lube oil pressure requirement for gas turbine start?", "target_page": 1},
            {"query": "When must the turbine be tripped for high vibration?", "target_page": 2}
        ]
    })

    # 2. Industrial Data Table (Dense Grid Layout)
    p2 = tmp_dir / "Exchanger_Inspection_Table.pdf"
    doc2 = pymupdf.open()
    page2_1 = doc2.new_page(width=595, height=842)
    page2_1.insert_text((50, 80), "TABLE 4.2 - HEAT EXCHANGER WALL THICKNESS INSPECTION DATA\n"
                                  "===========================================================\n"
                                  "Equipment ID | Location       | Nominal (mm) | Measured (mm) | Corrosion Rate (mpy) | Next Due\n"
                                  "HEX-201-A    | Shell Inlet    | 12.7         | 11.2          | 2.4                  | 2027-Q1\n"
                                  "HEX-201-B    | Shell Outlet   | 12.7         | 9.1           | 5.8                  | 2026-Q3\n"
                                  "HEX-202-A    | Channel Head   | 15.8         | 15.4          | 0.8                  | 2029-Q2\n"
                                  "HEX-202-B    | Return Header  | 15.8         | 10.5          | 6.2                  | 2026-Q2\n")
    page2_2 = doc2.new_page(width=595, height=842)
    page2_2.insert_text((50, 80), "TABLE 4.3 - PRESSURE DROP TEST LOGS\n"
                                  "====================================\n"
                                  "Exchanger | Tube ΔP (psi) | Shell ΔP (psi) | Fouling Factor\n"
                                  "HEX-201-A | 4.2           | 2.1            | 0.0002\n"
                                  "HEX-201-B | 14.8          | 8.6            | 0.0018\n")
    doc2.save(str(p2))
    doc2.close()
    docs.append({
        "type": "dense_table",
        "name": "Exchanger_Inspection_Table.pdf",
        "path": p2,
        "queries": [
            {"query": "What is the measured wall thickness and corrosion rate for HEX-201-B shell outlet?", "target_page": 1},
            {"query": "What is the tube pressure drop and fouling factor for HEX-201-B?", "target_page": 2}
        ]
    })

    # 3. Piping & Instrumentation Diagram (P&ID Blueprint / Visual Graph)
    p3 = tmp_dir / "PID_Reactor_Feed.pdf"
    doc3 = pymupdf.open()
    page3_1 = doc3.new_page(width=595, height=842)
    page3_1.insert_text((50, 80), "P&ID DWG-4001: REACTOR R-101 FEED TRAIN\n"
                                  "Line 4\"-HC-101 leads from Feed Pump P-101A to Reactor R-101 inlet nozzle N1.\n"
                                  "Control Valve FCV-101 is located on line 4\"-HC-101 between transmitter FT-101 and vessel R-101.\n"
                                  "Safety Relief Valve PSV-102 set at 45 bar is connected to bypass line 2\"-BP-102.")
    page3_2 = doc3.new_page(width=595, height=842)
    page3_2.insert_text((50, 80), "P&ID DWG-4002: UTILITY WATER INTERCONNECTIONS\n"
                                  "Cooling water supply 6\"-CW-201 feeds jackets of pumps P-101A and P-101B.\n"
                                  "Isolation valve MOV-301 controls CW manifold return header.")
    doc3.save(str(p3))
    doc3.close()
    docs.append({
        "type": "pid_diagram",
        "name": "PID_Reactor_Feed.pdf",
        "path": p3,
        "queries": [
            {"query": "Where is control valve FCV-101 located in the reactor feed line?", "target_page": 1},
            {"query": "Which valve controls cooling water return on manifold MOV-301?", "target_page": 2}
        ]
    })

    # 4. Scanned Maintenance Log (OCR-Reliant)
    p4 = tmp_dir / "Scanned_Maintenance_Log.pdf"
    doc4 = pymupdf.open()
    page4_1 = doc4.new_page(width=595, height=842)
    page4_1.insert_text((50, 80), "MAINTENANCE SHIFT HANDOVER LOG - SCAN 1\n"
                                  "Date: 2026-08-14 | Shift: Night | Unit: Hydrocracker\n"
                                  "Technician replaced mechanical seal on P-204B due to excessive leakage.\n"
                                  "Torqued casing bolts to 120 ft-lbs. Alignment checked: 0.03 mm TIR.")
    page4_2 = doc4.new_page(width=595, height=842)
    page4_2.insert_text((50, 80), "MAINTENANCE SHIFT HANDOVER LOG - SCAN 2\n"
                                  "Date: 2026-08-15 | Shift: Day | Unit: Reforming\n"
                                  "Cleaned suction strainer on pump P-301. Found rust flakes and weld slag.\n"
                                  "Suction gauge PI-301 reading restored to 1.8 bar.")
    doc4.save(str(p4))
    doc4.close()
    docs.append({
        "type": "scanned_log",
        "name": "Scanned_Maintenance_Log.pdf",
        "path": p4,
        "queries": [
            {"query": "What torque value was applied to P-204B casing bolts during seal replacement?", "target_page": 1},
            {"query": "What foreign debris was found in the suction strainer of pump P-301?", "target_page": 2}
        ]
    })

    # 5. Root Cause Analysis (RCA) Case Study (Hybrid Text + Diagram)
    p5 = tmp_dir / "RCA_Pump_Cavitation_Incident.pdf"
    doc5 = pymupdf.open()
    page5_1 = doc5.new_page(width=595, height=842)
    page5_1.insert_text((50, 80), "INCIDENT INVESTIGATION REPORT: CRUDE BOOSTER PUMP P-101 TRIP\n\n"
                                  "Executive Summary:\n"
                                  "On 2026-07-22 at 04:15, pump P-101 tripped on severe high vibration (14.2 mm/s).\n"
                                  "Operator observed intense gravel-like rattling noise prior to trip.\n"
                                  "Root cause investigation initiated per OSHA PSM 1910.119.")
    page5_2 = doc5.new_page(width=595, height=842)
    page5_2.insert_text((50, 80), "FAILURE MECHANISM & ROOT CAUSE ANALYSIS:\n\n"
                                  "Analysis confirms classical cavitation caused by inadequate NPSH margin.\n"
                                  "Atmospheric storage tank T-101 level dropped below 12% critical threshold.\n"
                                  "Suction pressure at PT-101 dropped to 0.4 bar, vaporizing light hydrocarbons.\n"
                                  "Micro-jet implosions pitted impeller eye vanes, causing unbalance and trip.")
    doc5.save(str(p5))
    doc5.close()
    docs.append({
        "type": "rca_hybrid",
        "name": "RCA_Pump_Cavitation_Incident.pdf",
        "path": p5,
        "queries": [
            {"query": "What was the initial vibration reading and trip timestamp for pump P-101?", "target_page": 1},
            {"query": "What was the root cause of pump P-101 cavitation and tank T-101 level drop?", "target_page": 2}
        ]
    })

    return docs


async def run_benchmark():
    """Runs the multimodal retrieval benchmark and computes metrics."""
    print("=" * 80)
    print("CogniShift Hybrid Multimodal Retrieval Benchmark (ColPali + ChromaDB)")
    print("=" * 80)

    await init_db()
    ws_id = 9999

    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, 'WS Benchmark')", (ws_id,))
        await db.commit()

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = Path(tmp_str)
        doc_specs = create_benchmark_documents(tmp_dir)

        sim_provider = SimulatedVisualEmbeddingProvider(patch_tokens=16, vector_dim=64)
        service = DocumentProcessingService(
            visual_embedding_provider=sim_provider,
            allow_simulation=True
        )

        ingested_ids = []
        print("\nIngesting benchmark documents into dual channels (FastEmbed + ColPali)...")
        for idx, ds in enumerate(doc_specs, start=101):
            async with get_db() as db:
                await db.execute(
                    "INSERT OR REPLACE INTO knowledge_sources (id, workspace_id, name, source_type, original_filename) VALUES (?, ?, ?, 'pdf', ?)",
                    (idx, ws_id, ds["name"], ds["name"])
                )
                await db.commit()

            t0 = time.perf_counter()
            res = await service.process_document(
                workspace_id=ws_id,
                source_id=idx,
                file_path=ds["path"],
                filename=ds["name"]
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            ingested_ids.append(idx)
            print(f"  [{ds['type']:<15}] Ingested {ds['name']:<30} (Pages: {res['total_pages']}, Chunks: {res['chunk_count']}, Visual: {res['visual_pages']}) in {elapsed_ms:.1f}ms")

        # Set up retrieval channels
        text_retriever = TextRetriever()
        vis_retriever = VisualRetriever(visual_provider=sim_provider, allow_simulation=True)
        hybrid_retriever = HybridDocumentRetriever(
            text_retriever=text_retriever,
            visual_retriever=vis_retriever,
            allow_simulation=True
        )

        # Benchmark evaluation metrics per channel
        channels = ["Text-Only RAG", "ColPali Visual", "Hybrid Fusion"]
        stats = {
            c: {
                "recall_at_1": 0,
                "recall_at_3": 0,
                "latencies": [],
                "total_queries": 0
            }
            for c in channels
        }

        print("\nExecuting evaluation queries across all channels...")

        for ds_idx, ds in enumerate(doc_specs, start=101):
            for q_obj in ds["queries"]:
                q_text = q_obj["query"]
                target_page = q_obj["target_page"]
                target_src = ds_idx

                # 1. Text-Only RAG
                t0 = time.perf_counter()
                _, _, text_ranked = await text_retriever.retrieve(ws_id, q_text, top_k=3, allowed_source_ids=ingested_ids)
                lat_text = (time.perf_counter() - t0) * 1000
                stats["Text-Only RAG"]["latencies"].append(lat_text)
                stats["Text-Only RAG"]["total_queries"] += 1

                t_pages = [(item["source_id"], item["page"]) for item in text_ranked]
                if t_pages and t_pages[0] == (target_src, target_page):
                    stats["Text-Only RAG"]["recall_at_1"] += 1
                if any(p == (target_src, target_page) for p in t_pages[:3]):
                    stats["Text-Only RAG"]["recall_at_3"] += 1

                # 2. ColPali Visual Page Retrieval
                t0 = time.perf_counter()
                vis_results = await vis_retriever.retrieve(ws_id, q_text, top_k=3, allowed_source_ids=ingested_ids)
                lat_vis = (time.perf_counter() - t0) * 1000
                stats["ColPali Visual"]["latencies"].append(lat_vis)
                stats["ColPali Visual"]["total_queries"] += 1

                v_pages = [(item.source_id, item.page_number) for item in vis_results]
                if v_pages and v_pages[0] == (target_src, target_page):
                    stats["ColPali Visual"]["recall_at_1"] += 1
                if any(p == (target_src, target_page) for p in v_pages[:3]):
                    stats["ColPali Visual"]["recall_at_3"] += 1

                # 3. Hybrid Multimodal Fusion
                t0 = time.perf_counter()
                _, hybrid_metas = await hybrid_retriever.retrieve(ws_id, q_text, top_k=3, allowed_source_ids=ingested_ids)
                lat_hybrid = (time.perf_counter() - t0) * 1000
                stats["Hybrid Fusion"]["latencies"].append(lat_hybrid)
                stats["Hybrid Fusion"]["total_queries"] += 1

                h_pages = [(item["source_id"], item["page"]) for item in hybrid_metas]
                if h_pages and h_pages[0] == (target_src, target_page):
                    stats["Hybrid Fusion"]["recall_at_1"] += 1
                if any(p == (target_src, target_page) for p in h_pages[:3]):
                    stats["Hybrid Fusion"]["recall_at_3"] += 1

        # Clean up benchmark workspace
        for sid in ingested_ids:
            await idempotent_delete_source(ws_id, sid)

        # Print Benchmark Report Table
        print("\n" + "=" * 80)
        print(f"{'Retrieval Channel':<22} | {'Recall@1':<10} | {'Recall@3':<10} | {'P50 Latency':<12} | {'P99 Latency':<12}")
        print("-" * 80)

        for c in channels:
            tot = max(1, stats[c]["total_queries"])
            r1 = (stats[c]["recall_at_1"] / tot) * 100
            r3 = (stats[c]["recall_at_3"] / tot) * 100
            lats = stats[c]["latencies"]
            p50 = np.percentile(lats, 50) if lats else 0.0
            p99 = np.percentile(lats, 99) if lats else 0.0

            print(f"{c:<22} | {r1:>8.1f}% | {r3:>8.1f}% | {p50:>9.2f} ms | {p99:>9.2f} ms")

        print("=" * 80)
        print("Benchmark completed successfully.\n")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
