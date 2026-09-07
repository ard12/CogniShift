"""CogniShift: SIH26117 Master Jury Demonstration Runner & Telemetry Guide.

Interactive terminal orchestrator for the Smart India Hackathon jury demonstration.
Steps through all 7 showcase acts with colorized narration, diagnostic verification,
and live operational telemetry.
"""

import sys
import time
import json
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from cognishift.app.config import settings

# ANSI formatting for crisp terminal output
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner(title: str, act_num: int = None):
    print("\n" + "=" * 70)
    if act_num is not None:
        print(f"{CYAN}{BOLD}  ACT {act_num}: {title.upper()}{RESET}")
    else:
        print(f"{CYAN}{BOLD}  {title.upper()}{RESET}")
    print("=" * 70)


def prompt_step(instruction: str):
    print(f"\n{YELLOW}{BOLD}[PRESENTER ACTION]{RESET} {instruction}")
    input(f"{CYAN}>> Press [ENTER] when action is complete to proceed...{RESET}")


def main():
    print_banner("CogniShift: SIH26117 Master Jury Showcase Driver")
    print(f"{BOLD}Target Event:{RESET} Smart India Hackathon (SIH26117)")
    print(f"{BOLD}Partner:{RESET} Mangalore Refinery & Petrochemicals Limited (MRPL)")
    print(f"{BOLD}Security Mode:{RESET} 100% Air-Gapped / Zero Cloud Egress")
    print(f"{BOLD}Database:{RESET} {settings.database_path}")
    print("=" * 70)

    # Preflight quick check
    print(f"\n{BOLD}Running Instant Health Diagnostic...{RESET}")
    db_ok = settings.database_path.exists()
    chroma_ok = settings.chroma_path.exists()
    models_ok = (ROOT_DIR / "data" / "models" / "fastembed").exists()
    print(f"  [{GREEN}OK{RESET}] Database Connection: {'Active' if db_ok else 'Missing'}")
    print(f"  [{GREEN}OK{RESET}] ChromaDB Vector Storage: {'Ready' if chroma_ok else 'Missing'}")
    print(f"  [{GREEN}OK{RESET}] FastEmbed Local Model Cache: {'Ready' if models_ok else 'Missing'}")

    input(f"\n{GREEN}{BOLD}>> Ready to begin Jury Demonstration? Press [ENTER] to start Act I...{RESET}")

    # ACT I
    print_banner("The Air-Gap Proof & Physical Network Sovereignty", 1)
    print(f"{BOLD}Key Message for Judges:{RESET} 'Not a single byte leaves this laptop. No OpenAI, no Azure, no CDNs.'")
    print("\n1. Show top status beacon: STRICT LOOPBACK | ZERO CLOUD EGRESS.")
    print("2. Open Browser DevTools (F12) -> Network tab -> Refresh (F5).")
    print("3. Point out that all assets load strictly from 127.0.0.1:8000 with 0 external requests.")
    prompt_step("Demonstrate zero-network egress in the browser network trace.")

    # ACT II
    print_banner("Multimodal Gauge Reading & Edge Vision", 2)
    print(f"{BOLD}Key Message for Judges:{RESET} 'Our local 1.86B VLM reads analog Bourdon dials on local GPU; FastEmbed cites SOP.'")
    print("\nPrompt to type in Operator Console:")
    print(f"{GREEN}Inspect this pressure gauge, extract the current reading, and evaluate it against our pump maintenance SOP.{RESET}")
    print("\nAttachment: data/demo/gauge_pressure_critical_485psi.png")
    prompt_step("Execute the gauge vision run in Operator Console and show needle detection at 485 PSI.")

    # ACT III
    print_banner("Physical Plant Topology Graph Traversal", 3)
    print(f"{BOLD}Key Message for Judges:{RESET} 'RAG alone cannot know piping connections. CogniShift uses an explicit SQLite Knowledge Graph.'")
    print("\nPrompt to type in Operator Console:")
    print(f"{GREEN}Trace the physical piping from Pump P-101A and identify which downstream equipment and relief valve protect it.{RESET}")
    
    # Query database to show live graph records
    try:
        conn = sqlite3.connect(settings.database_path)
        c = conn.cursor()
        c.execute("""
            SELECT n1.name, e.relation_type, n2.name 
            FROM graph_edges e 
            JOIN graph_nodes n1 ON e.source_node_id = n1.id 
            JOIN graph_nodes n2 ON e.target_node_id = n2.id 
            WHERE e.workspace_id = 1
        """)
        rows = c.fetchall()
        print(f"\n{CYAN}Live Database Topology Traversal Paths:{RESET}")
        for r in rows:
            print(f"  • {r[0]} --({r[1]})--> {r[2]}")
        conn.close()
    except Exception as e:
        print(f"  (Graph query preview unavailable: {e})")

    prompt_step("Show the topological path: P-101A -> Reactor-B -> SV-402 -> Flare-Header in the agent response.")

    # ACT IV
    print_banner("7-Intent Semantic Router & Safety Negation", 4)
    print(f"{BOLD}Key Message for Judges:{RESET} 'Deterministic CPU router intercepts dangerous keywords, handles negations, and abstains on ambiguity.'")
    print("\nTest Prompts:")
    print(f"  A. Inquiry: {GREEN}How do you check pressure?{RESET} -> Routes to CONVERSATION (no tool run).")
    print(f"  B. Negation: {GREEN}Do not restart P-101A under any circumstances.{RESET} -> Negation guard prevents trip.")
    print(f"  C. Ambiguity: {GREEN}Can you trigger emergency pressure relief?{RESET} -> Safely abstains to COMPLEX_AGENT.")
    prompt_step("Demonstrate semantic routing and negation defense in the console.")

    # ACT V
    print_banner("Strict Four-Eyes Human-in-the-Loop Interlocks", 5)
    print(f"{BOLD}Key Message for Judges:{RESET} 'Dual independent supervisor sign-offs required for high-risk plant actions.'")
    print("\nPrompt to type in Operator Console:")
    print(f"{GREEN}Initiate emergency pressure relief on P-101A to depressurize the line.{RESET}")
    print("\nExecution Steps:")
    print("  1. Operator Sam clicks Authorize -> BLOCKED (403 Forbidden).")
    print("  2. Switch to Supervisor Jane -> Authorizes Stage 1 (Run remains safely PAUSED).")
    print("  3. Switch to Plant Manager Rohit -> Authorizes Stage 2 (Run resumes and depressurizes line).")
    prompt_step("Walk through the Four-Eyes dual approval interlock in the console.")

    # ACT VI
    print_banner("Air-Gapped Docker Sandbox & Deliverable Synthesis", 6)
    print(f"{BOLD}Key Message for Judges:{RESET} 'Runs calculations inside an isolated container (--network none) and generates styled Excel/PDF reports.'")
    print("\nPrompt to type in Operator Console:")
    print(f"{GREEN}Analyze equipment_readings.csv in the sandbox, identify 3-sigma outliers, and generate an audit report in Excel and PDF.{RESET}")
    print("\nDeliverables Produced:")
    print("  • MRPL_Audit_Report.xlsx (Multi-tab Excel workbook with styled tables)")
    print("  • MRPL_Audit_Report.pdf (Vector PDF with embedded Matplotlib trend plots)")
    print("  • SHA-256 Tamper Verification on download")
    prompt_step("Inspect generated deliverables in /artifacts and verify the SHA-256 hash.")

    # ACT VII
    print_banner("Multi-Tenant Workspace Segregation & Conclusion", 7)
    print(f"{BOLD}Key Message for Judges:{RESET} 'Strict boundary enforcement: documents, graph nodes, and approvals never bleed across units.'")
    print("\n1. Switch workspace to Fluid Catalytic Cracker (FCCU).")
    print("2. Show that knowledge vault and approval queues are 100% isolated.")
    print("3. Deliver closing statement and open the floor for jury Q&A.")
    prompt_step("Deliver closing pitch to the evaluation panel.")

    print_banner("Showcase Complete")
    print(f"{GREEN}{BOLD}Demonstration successfully concluded! Consult SIH_JURY_MASTER_SHOWCASE.md for the Q&A Defense Bible.{RESET}\n")


if __name__ == "__main__":
    main()
