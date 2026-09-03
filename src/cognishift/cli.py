"""CogniShift CLI: Industrial Command-Line Interface for Sovereign Agentic Workbench."""
import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich import box

from cognishift.app.config import settings
from cognishift.app.db.database import get_db, init_db
from cognishift.core.engine import execute_agent_run, resume_agent_run
from cognishift.core.retriever import retrieve_context, process_pdf
from cognishift.core.graph_memory import query_graph_context
from cognishift.core.tools import (
    execute_tool,
    load_tep_telemetry,
    load_maintenance_orders,
    load_refinery_topology,
)
from cognishift.core.providers import get_provider

# Initialize Rich Console and Typer App
console = Console()
app = typer.Typer(
    name="cognishift",
    help="CogniShift: Sovereign On-Premise Agentic AI Workbench for Industrial Operations",
    add_completion=False,
)

# Sub-typer groups
workspace_app = typer.Typer(help="Manage segregated industrial workspaces")
agent_app = typer.Typer(help="Inspect and configure industrial agents")
knowledge_app = typer.Typer(help="Manage PDF manuals, chunking, and vector RAG")
graph_app = typer.Typer(help="Query ISO 15926 / ISA-95 Plant Topology Knowledge Graph")
telemetry_app = typer.Typer(help="Inspect SCADA telemetry and SAP PM work orders")
run_app = typer.Typer(help="Execute reasoning loops and view execution timelines")
approvals_app = typer.Typer(help="Review and authorize Four-Eyes HITL safety requests")

app.add_typer(workspace_app, name="workspace")
app.add_typer(agent_app, name="agent")
app.add_typer(knowledge_app, name="knowledge")
app.add_typer(graph_app, name="graph")
app.add_typer(telemetry_app, name="telemetry")
app.add_typer(run_app, name="run")
app.add_typer(approvals_app, name="approvals")


# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def print_banner():
    banner_text = (
        "[bold cyan]COGNISHIFT[/bold cyan] [bold green]v0.1.0[/bold green] "
        "| [bold yellow]Sovereign On-Premise Agentic AI Workbench[/bold yellow]\n"
        "[dim]MRPL Industrial Operations | IEC 62443 Level 3.5 | Air-Gapped Zero-Cloud[/dim]"
    )
    console.print(Panel(banner_text, border_style="cyan", box=box.ROUNDED))


def run_async(coro):
    """Run an async coroutine synchronously inside Typer commands."""
    return asyncio.run(coro)


# -----------------------------------------------------------------------------
# 1. SYSTEM & STATUS COMMANDS
# -----------------------------------------------------------------------------
@app.command("status")
def system_status():
    """Inspect local GPU health, Ollama models, database state, and air-gap sovereignty."""
    print_banner()

    async def _status():
        await init_db()
        provider = get_provider()
        health = await provider.health_check()
        info = await provider.model_info()

        # Database counts
        async with get_db() as db:
            counts = {}
            for table in [
                "workspaces",
                "agent_definitions",
                "knowledge_sources",
                "tool_definitions",
                "agent_runs",
                "approval_requests",
                "graph_nodes",
                "graph_edges",
            ]:
                try:
                    c = await db.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                    counts[table] = (await c.fetchone())["cnt"]
                except Exception:
                    counts[table] = 0

        # Status Table
        table = Table(title="System & Sovereignty Diagnostics", box=box.ROUNDED)
        table.add_column("Component", style="cyan", no_wrap=True)
        table.add_column("Status / Setting", style="bold")
        table.add_column("Details", style="dim")

        table.add_row(
            "Operating Mode",
            f"[green]{settings.operating_mode.upper()}[/green]",
            "Strict zero cloud egress enforced",
        )
        table.add_row(
            "Database Engine",
            "[green]SQLite 3 (aiosqlite)[/green]",
            f"{settings.database_path} (WAL Mode enabled)",
        )
        table.add_row(
            "Vector Engine",
            "[green]ChromaDB + FastEmbed[/green]",
            f"{settings.chroma_path} (BAAI/bge-small-en-v1.5)",
        )

        ollama_status = (
            "[bold green]ONLINE (GPU)[/bold green]" if health else "[bold red]OFFLINE[/bold red]"
        )
        table.add_row("Ollama Inference", ollama_status, settings.ollama_base_url)
        table.add_row("Text Model", settings.text_model, "Primary reasoning SLM")
        table.add_row("Vision Model", settings.vision_model, "Gauge inspection & OCR VLM")

        models_str = ", ".join(info.get("models", [])) or "None detected"
        table.add_row("Available Models", f"[yellow]{models_str}[/yellow]", "Local weight catalog")

        console.print(table)

        # DB Statistics Table
        db_table = Table(title="Database Relational Storage", box=box.ROUNDED)
        db_table.add_column("Table Name", style="cyan")
        db_table.add_column("Active Rows", style="magenta", justify="right")

        for tbl, cnt in counts.items():
            db_table.add_row(tbl, str(cnt))

        console.print(db_table)

    run_async(_status())


# -----------------------------------------------------------------------------
# 2. WORKSPACE COMMANDS
# -----------------------------------------------------------------------------
@workspace_app.command("list")
def list_workspaces():
    """List all segregated refinery workspaces."""
    async def _list():
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM workspaces ORDER BY id ASC")
            rows = await cursor.fetchall()

        table = Table(title="Refinery Workspaces", box=box.ROUNDED)
        table.add_column("ID", style="bold cyan", justify="center", width=4)
        table.add_column("Workspace Name", style="green", no_wrap=True)
        table.add_column("Description", style="dim")
        table.add_column("Mode", style="yellow")
        table.add_column("Created", style="dim")

        for r in rows:
            table.add_row(str(r["id"]), r["name"], r["description"] or "—", r["operating_mode"], str(r["created_at"]))

        console.print(table)

    run_async(_list())


@workspace_app.command("create")
def create_workspace(
    name: str = typer.Argument(..., help="Name of the new workspace"),
    description: str = typer.Option("", "--desc", "-d", help="Description of the refinery unit"),
):
    """Provision a new segregated industrial workspace."""
    async def _create():
        async with get_db() as db:
            cursor = await db.execute(
                "INSERT INTO workspaces (name, description, operating_mode) VALUES (?, ?, 'local') RETURNING *",
                (name, description),
            )
            row = await cursor.fetchone()
            await db.commit()
            console.print(f"[bold green][OK] Workspace '{row['name']}' created successfully (ID: {row['id']})![/bold green]")

    run_async(_create())


# -----------------------------------------------------------------------------
# 3. AGENT COMMANDS
# -----------------------------------------------------------------------------
@agent_app.command("list")
def list_agents(
    workspace_id: Optional[int] = typer.Option(None, "--workspace", "-w", help="Filter by workspace ID"),
):
    """List registered agents and their assigned models and tool gates."""
    async def _list():
        async with get_db() as db:
            query = "SELECT * FROM agent_definitions"
            params = ()
            if workspace_id:
                query += " WHERE workspace_id = ?"
                params = (workspace_id,)
            query += " ORDER BY id ASC"

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

        table = Table(title="Industrial Agents Registry", box=box.ROUNDED)
        table.add_column("ID", style="bold cyan", justify="center", width=4)
        table.add_column("Workspace", style="dim", justify="center", width=10)
        table.add_column("Agent Name", style="green", no_wrap=True)
        table.add_column("Model", style="yellow")
        table.add_column("HITL Gate", justify="center")
        table.add_column("Status", style="bold")

        for r in rows:
            hitl_badge = "[bold red]REQUIRED[/bold red]" if r["approval_required"] else "[green]Auto-Run[/green]"
            table.add_row(
                str(r["id"]),
                str(r["workspace_id"]),
                r["name"],
                r["model_name"],
                hitl_badge,
                r["status"],
            )

        console.print(table)

    run_async(_list())


@agent_app.command("info")
def agent_info(agent_id: int = typer.Argument(..., help="Agent definition ID")):
    """View detailed configuration and system instructions for an agent."""
    async def _info():
        async with get_db() as db:
            cursor = await db.execute("SELECT * FROM agent_definitions WHERE id = ?", (agent_id,))
            agent = await cursor.fetchone()
            if not agent:
                console.print(f"[bold red]Error: Agent #{agent_id} not found.[/bold red]")
                return

        panel_content = (
            f"[bold cyan]Name:[/bold cyan] {agent['name']}\n"
            f"[bold cyan]Workspace ID:[/bold cyan] {agent['workspace_id']}\n"
            f"[bold cyan]Model:[/bold cyan] {agent['model_name']}\n"
            f"[bold cyan]Approval Required:[/bold cyan] {'YES' if agent['approval_required'] else 'NO'}\n"
            f"[bold cyan]Allowed Tools:[/bold cyan] {agent['allowed_tool_ids']}\n\n"
            f"[bold yellow]System Instructions:[/bold yellow]\n{agent['system_instructions']}"
        )
        console.print(Panel(panel_content, title=f"Agent Details: #{agent_id} - {agent['name']}", border_style="cyan"))

    run_async(_info())


# -----------------------------------------------------------------------------
# 4. KNOWLEDGE & RAG COMMANDS
# -----------------------------------------------------------------------------
@knowledge_app.command("list")
def list_knowledge(
    workspace_id: Optional[int] = typer.Option(1, "--workspace", "-w", help="Workspace ID"),
):
    """List ingested PDF technical manuals and chunk counts."""
    async def _list():
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM knowledge_sources WHERE workspace_id = ? ORDER BY id ASC",
                (workspace_id,),
            )
            rows = await cursor.fetchall()

        table = Table(title=f"Knowledge Sources (Workspace #{workspace_id})", box=box.ROUNDED)
        table.add_column("ID", style="bold cyan", width=4)
        table.add_column("Document Name", style="green")
        table.add_column("Filename", style="dim")
        table.add_column("Status", style="yellow")
        table.add_column("Vector Chunks", style="magenta", justify="right")
        table.add_column("Ingested At", style="dim")

        for r in rows:
            status_style = "[green]completed[/green]" if r["processing_status"] == "completed" else "[yellow]pending[/yellow]"
            table.add_row(
                str(r["id"]),
                r["name"],
                r["original_filename"],
                status_style,
                str(r["chunk_count"]),
                str(r["created_at"]),
            )

        console.print(table)

    run_async(_list())


@knowledge_app.command("upload")
def upload_manual(
    file_path: str = typer.Argument(..., help="Path to PDF manual file"),
    workspace_id: int = typer.Option(1, "--workspace", "-w", help="Target workspace ID"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Friendly name for manual"),
):
    """Ingest a PDF manual, compute FastEmbed embeddings, and store in ChromaDB."""
    pdf_file = Path(file_path)
    if not pdf_file.exists():
        console.print(f"[bold red]Error: File '{file_path}' does not exist.[/bold red]")
        raise typer.Exit(1)

    doc_name = name or pdf_file.stem

    async def _upload():
        with console.status(f"[bold cyan]Ingesting and embedding '{pdf_file.name}' into ChromaDB...[/bold cyan]", spinner="dots"):
            async with get_db() as db:
                cursor = await db.execute(
                    """INSERT INTO knowledge_sources
                       (workspace_id, name, source_type, original_filename, local_path, processing_status)
                       VALUES (?, ?, 'pdf', ?, ?, 'processing') RETURNING id""",
                    (workspace_id, doc_name, pdf_file.name, str(pdf_file)),
                )
                source_id = (await cursor.fetchone())["id"]
                await db.commit()

            chunks_processed = await process_pdf(
                file_path=str(pdf_file),
                workspace_id=workspace_id,
                source_id=source_id,
                filename=pdf_file.name,
            )

            async with get_db() as db:
                await db.execute(
                    """UPDATE knowledge_sources
                       SET processing_status = 'completed', chunk_count = ?
                       WHERE id = ?""",
                    (chunks_processed, source_id),
                )
                await db.commit()

        console.print(
            f"[bold green][OK] Ingested '{pdf_file.name}' successfully! "
            f"Created [magenta]{chunks_processed}[/magenta] vector chunks in workspace #{workspace_id}.[/bold green]"
        )

    run_async(_upload())


@knowledge_app.command("search")
def search_knowledge(
    query: str = typer.Argument(..., help="Query to search against manuals"),
    workspace_id: int = typer.Option(1, "--workspace", "-w", help="Workspace ID"),
    top_k: int = typer.Option(3, "--top-k", "-k", help="Number of chunks to retrieve"),
):
    """Perform direct Vector RAG retrieval with exact page citations."""
    async def _search():
        with console.status(f"[bold cyan]Searching manuals for: '{query}'...[/bold cyan]", spinner="dots"):
            ctx = await retrieve_context(workspace_id=workspace_id, query=query, top_k=top_k)

        if not ctx:
            console.print("[yellow]No relevant context found in manuals.[/yellow]")
            return

        console.print(Panel(ctx, title="Retrieved Manual Sections & Citations", border_style="green", box=box.ROUNDED))

    run_async(_search())


# -----------------------------------------------------------------------------
# 5. PLANT TOPOLOGY GRAPH COMMANDS
# -----------------------------------------------------------------------------
@graph_app.command("query")
def query_graph(
    tag: str = typer.Argument(..., help="Equipment tag or query (e.g., Pump-101A, Reactor-B)"),
    workspace_id: int = typer.Option(1, "--workspace", "-w", help="Workspace ID"),
    hops: int = typer.Option(2, "--hops", help="Max relationship traversal hops"),
):
    """Query ISO 15926 Plant Topology Knowledge Graph for physical equipment connections."""
    async def _query():
        with console.status(f"[bold cyan]Traversing topology graph for '{tag}'...[/bold cyan]", spinner="dots"):
            graph_ctx = await query_graph_context(workspace_id=workspace_id, query_text=tag, max_hops=hops)

        if not graph_ctx:
            console.print(f"[yellow]No topology connections found for '{tag}' in workspace #{workspace_id}.[/yellow]")
            return

        console.print(Panel(graph_ctx, title=f"Plant Topology Graph: {tag} ({hops}-Hop)", border_style="cyan", box=box.ROUNDED))

    run_async(_query())


@graph_app.command("stats")
def graph_stats(
    workspace_id: int = typer.Option(1, "--workspace", "-w", help="Workspace ID"),
):
    """View graph memory node types and edge relationship statistics."""
    async def _stats():
        async with get_db() as db:
            c1 = await db.execute(
                "SELECT entity_type, COUNT(*) as cnt FROM graph_nodes WHERE workspace_id = ? GROUP BY entity_type",
                (workspace_id,),
            )
            node_types = await c1.fetchall()

            c2 = await db.execute(
                "SELECT relation_type, COUNT(*) as cnt FROM graph_edges WHERE workspace_id = ? GROUP BY relation_type",
                (workspace_id,),
            )
            edge_types = await c2.fetchall()

        table1 = Table(title="Graph Nodes by Entity Type", box=box.ROUNDED)
        table1.add_column("Entity Type", style="cyan")
        table1.add_column("Count", style="green", justify="right")
        for r in node_types:
            table1.add_row(r["entity_type"], str(r["cnt"]))

        table2 = Table(title="Graph Edges by Relation Type", box=box.ROUNDED)
        table2.add_column("Relation Type", style="yellow")
        table2.add_column("Count", style="green", justify="right")
        for r in edge_types:
            table2.add_row(r["relation_type"], str(r["cnt"]))

        console.print(table1)
        console.print(table2)

    run_async(_stats())


# -----------------------------------------------------------------------------
# 6. SCADA TELEMETRY & SAP PM COMMANDS
# -----------------------------------------------------------------------------
@telemetry_app.command("check")
def check_sensor(
    sensor_id: str = typer.Argument(..., help="Instrument sensor tag (e.g., PT-101, TT-204)"),
):
    """Check live reading of an industrial sensor from SCADA telemetry stream."""
    async def _check():
        reading = await execute_tool("check_pressure" if "PT" in sensor_id.upper() else "check_temperature", {"sensor_id": sensor_id})
        is_alert = "CRITICAL" in reading or "SURGE" in reading
        style = "bold red" if is_alert else "bold green"
        console.print(Panel(reading, title=f"Telemetry Reading: {sensor_id}", border_style="red" if is_alert else "green"))

    run_async(_check())


@telemetry_app.command("stream")
def telemetry_stream():
    """Inspect all latest dynamic SCADA telemetry sensor readings."""
    data = load_tep_telemetry()
    scenarios = data.get("scenarios", [])

    table = Table(title="Tennessee Eastman Process SCADA Telemetry Stream", box=box.ROUNDED)
    table.add_column("Scenario / Fault", style="dim", width=20)
    table.add_column("Sensor Tag", style="cyan", no_wrap=True)
    table.add_column("Current Reading", style="bold")
    table.add_column("Health Status", justify="center")

    for sc in scenarios:
        sc_name = f"{sc.get('scenario_id', '')} ({sc.get('fault_code', '')})"
        for pt in sc.get("telemetry_points", []):
            st = pt.get("status", "GOOD")
            st_badge = "[green]NORMAL (Nominal)[/green]" if st == "GOOD" else f"[bold red]{st}[/bold red]"
            table.add_row(sc_name, pt.get("sensor", ""), f"{pt.get('value')} {pt.get('unit', '')}", st_badge)

    console.print(table)


@telemetry_app.command("orders")
def sap_orders():
    """List SAP S/4HANA PM work orders and ISO 14224 FMEA damage records."""
    data = load_maintenance_orders()
    orders = data.get("orders", [])

    table = Table(title="SAP S/4HANA PM Maintenance Orders", box=box.ROUNDED)
    table.add_column("Order #", style="cyan", width=12)
    table.add_column("Equipment", style="yellow")
    table.add_column("Notification Type", style="dim")
    table.add_column("Damage Code", style="bold")
    table.add_column("Status", style="green")

    for o in orders:
        table.add_row(
            str(o.get("order_number", "")),
            str(o.get("equipment_tag", "")),
            str(o.get("notification_type", "")),
            str(o.get("damage_code", "")),
            str(o.get("system_status", "")),
        )

    console.print(table)


# -----------------------------------------------------------------------------
# 7. AGENT EXECUTION (RUN) COMMANDS
# -----------------------------------------------------------------------------
@run_app.command("execute")
def run_prompt(
    prompt: str = typer.Argument(..., help="Prompt instruction for the agent"),
    agent_id: int = typer.Option(1, "--agent", "-a", help="Agent ID"),
    workspace_id: int = typer.Option(1, "--workspace", "-w", help="Workspace ID"),
    image: Optional[str] = typer.Option(None, "--image", "-i", help="Path to field photo/image for multimodal inspection"),
    user_id: str = typer.Option("operator", "--user", "-u", help="Operator ID"),
):
    """Execute an autonomous reasoning run with multimodal vision and HITL safety."""
    async def _run():
        console.print(f"\n[bold cyan]>>> Initiating Agent Run (Workspace #{workspace_id}, Agent #{agent_id})...[/bold cyan]")
        if image:
            console.print(f"[magenta][IMAGE] Multimodal Input Attached: {image}[/magenta]")

        with console.status("[bold green]Executing agent reasoning loop on local GPU...[/bold green]", spinner="dots"):
            response = await execute_agent_run(
                workspace_id=workspace_id,
                agent_id=agent_id,
                input_text=prompt,
                user_id=user_id,
                input_image_path=image,
            )

        run_id = response.id
        status = response.status

        if status == "paused":
            console.print(
                Panel(
                    f"[bold red][HITL GATE] SAFETY INTERLOCK TRIGGERED (Four-Eyes Principle)[/bold red]\n\n"
                    f"Execution is [bold yellow]PAUSED[/bold yellow] awaiting Shift Supervisor authorization.\n\n"
                    f"[bold cyan]Action:[/bold cyan] {response.result_text}\n"
                    f"[bold cyan]Run ID:[/bold cyan] {run_id}\n\n"
                    f"[dim]To authorize: run `cognishift approvals approve <request_id>`[/dim]",
                    title=f"Run #{run_id}: PAUSED AT HITL GATE",
                    border_style="red",
                    box=box.ROUNDED,
                )
            )
        else:
            console.print(
                Panel(
                    f"[bold green]Status: {status.upper()}[/bold green]\n\n"
                    f"{response.result_text}\n\n"
                    f"[dim]Citations: {response.sources_used or 'None'}[/dim]",
                    title=f"Run #{run_id} Response ({response.model_name})",
                    border_style="green",
                    box=box.ROUNDED,
                )
            )

    run_async(_run())


@run_app.command("history")
def run_history(
    workspace_id: int = typer.Option(1, "--workspace", "-w", help="Workspace ID"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of past runs to retrieve"),
):
    """View past agent runs, results, and audit status."""
    async def _history():
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT id, agent_id, user_id, input_text, status, model_name, started_at
                   FROM agent_runs WHERE workspace_id = ? ORDER BY id DESC LIMIT ?""",
                (workspace_id, limit),
            )
            runs = await cursor.fetchall()

        table = Table(title=f"Execution History (Workspace #{workspace_id})", box=box.ROUNDED)
        table.add_column("Run ID", style="cyan", justify="center", width=6)
        table.add_column("Operator", style="dim", width=10)
        table.add_column("Input Instruction", style="bold")
        table.add_column("Status", justify="center")
        table.add_column("Model", style="yellow")
        table.add_column("Started At", style="dim")

        for r in runs:
            st = r["status"]
            badge = "[green]completed[/green]" if st == "completed" else ("[yellow]paused[/yellow]" if st == "paused" else "[red]failed[/red]")
            table.add_row(str(r["id"]), r["user_id"], r["input_text"][:50] + ("..." if len(r["input_text"]) > 50 else ""), badge, r["model_name"], str(r["started_at"]))

        console.print(table)

    run_async(_history())


@run_app.command("events")
def run_events(run_id: int = typer.Argument(..., help="Run ID")):
    """Stream step-by-step audit event ledger for an execution run."""
    async def _events():
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT event_type, message, created_at FROM run_events WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            )
            events = await cursor.fetchall()

        if not events:
            console.print(f"[yellow]No events logged for Run #{run_id}.[/yellow]")
            return

        table = Table(title=f"Event Sourcing Timeline: Run #{run_id}", box=box.ROUNDED)
        table.add_column("Event Type", style="cyan", width=22)
        table.add_column("Message / State Mutation", style="white")
        table.add_column("Timestamp", style="dim", width=20)

        for e in events:
            table.add_row(e["event_type"], e["message"], str(e["created_at"]))

        console.print(table)

    run_async(_events())


@run_app.command("resume")
def resume_run(run_id: int = typer.Argument(..., help="Paused Run ID to resume")):
    """Resume execution of an approved run."""
    async def _resume():
        with console.status(f"[bold cyan]Resuming Run #{run_id} after supervisor authorization...[/bold cyan]", spinner="dots"):
            resp = await resume_agent_run(run_id)

        console.print(
            Panel(
                f"[bold green]Status: {resp.status.upper()}[/bold green]\n\n"
                f"{resp.result_text}\n\n"
                f"[dim]Citations: {resp.sources_used}[/dim]",
                title=f"Run #{run_id} Resumed & Completed",
                border_style="green",
                box=box.ROUNDED,
            )
        )

    run_async(_resume())


# -----------------------------------------------------------------------------
# 8. FOUR-EYES SAFETY & APPROVALS COMMANDS
# -----------------------------------------------------------------------------
@approvals_app.command("list")
def list_approvals():
    """List pending supervisor approval requests awaiting authorization."""
    async def _list():
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT a.id, a.run_id, t.name as tool_name, a.risk_level, a.request_reason, a.status, a.requested_at
                   FROM approval_requests a
                   JOIN tool_definitions t ON a.tool_id = t.id
                   WHERE a.status = 'pending'
                   ORDER BY a.id ASC"""
            )
            rows = await cursor.fetchall()

        if not rows:
            console.print("[bold green][OK] Zero pending approval requests. All systems nominal.[/bold green]")
            return

        table = Table(title="Four-Eyes Safety Gate: Pending Approvals", box=box.ROUNDED)
        table.add_column("Req ID", style="bold red", justify="center", width=8)
        table.add_column("Run ID", style="cyan", justify="center", width=8)
        table.add_column("Hazardous Action", style="bold yellow")
        table.add_column("Risk Level", style="bold red")
        table.add_column("Request Reason", style="white")
        table.add_column("Requested At", style="dim")

        for r in rows:
            table.add_row(
                str(r["id"]),
                str(r["run_id"]),
                r["tool_name"],
                r["risk_level"].upper(),
                r["request_reason"],
                str(r["requested_at"]),
            )

        console.print(table)

    run_async(_list())


@approvals_app.command("approve")
def approve_action(
    request_id: int = typer.Argument(..., help="Approval Request ID"),
    reviewer: str = typer.Option("SUPERVISOR-3410", "--reviewer", "-r", help="Supervisor Employee ID"),
):
    """Sign off and authorize a high-risk action, automatically resuming execution."""
    async def _approve():
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM approval_requests WHERE id = ? AND status = 'pending'",
                (request_id,),
            )
            req = await cursor.fetchone()
            if not req:
                console.print(f"[bold red]Error: Pending approval request #{request_id} not found.[/bold red]")
                return

            run_id = req["run_id"]
            await db.execute(
                """UPDATE approval_requests
                   SET status = 'approved', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (reviewer, request_id),
            )
            await db.commit()

        console.print(f"[bold green][OK] Request #{request_id} APPROVED by {reviewer}. Resuming Run #{run_id}...[/bold green]")
        resp = await resume_agent_run(run_id)
        console.print(
            Panel(
                f"[bold green]Action Executed Successfully![/bold green]\n\n"
                f"{resp.result_text}",
                title=f"Run #{run_id} Restored & Resolved",
                border_style="green",
            )
        )

    run_async(_approve())


@approvals_app.command("reject")
def reject_action(
    request_id: int = typer.Argument(..., help="Approval Request ID"),
    reviewer: str = typer.Option("SUPERVISOR-3410", "--reviewer", "-r", help="Supervisor Employee ID"),
):
    """Reject a hazardous action and abort tool execution."""
    async def _reject():
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM approval_requests WHERE id = ? AND status = 'pending'",
                (request_id,),
            )
            req = await cursor.fetchone()
            if not req:
                console.print(f"[bold red]Error: Pending approval request #{request_id} not found.[/bold red]")
                return

            run_id = req["run_id"]
            await db.execute(
                """UPDATE approval_requests
                   SET status = 'rejected', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (reviewer, request_id),
            )
            await db.execute(
                """UPDATE agent_runs
                   SET status = 'cancelled', result_text = 'Action rejected by supervisor.', completed_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (run_id,),
            )
            await db.commit()

        console.print(f"[bold yellow][REJECTED] Request #{request_id} REJECTED by {reviewer}. Run #{run_id} cancelled safely.[/bold yellow]")

    run_async(_reject())


# -----------------------------------------------------------------------------
# 9. INTERACTIVE REPL MODE (CHAT)
# -----------------------------------------------------------------------------
@app.command("chat")
def interactive_chat(
    workspace_id: int = typer.Option(1, "--workspace", "-w", help="Workspace ID"),
    agent_id: int = typer.Option(1, "--agent", "-a", help="Agent ID"),
):
    """Launch interactive operator chat console in your terminal."""
    print_banner()
    console.print(
        f"[bold green]Interactive Terminal Session Started[/bold green] "
        f"(Workspace #{workspace_id}, Agent #{agent_id})\n"
        "[dim]Type your question or instruction. Available commands:\n"
        "  /image <path>   - Inspect an equipment photo or gauge dial\n"
        "  /status         - Show system health\n"
        "  /approvals      - View pending safety requests\n"
        "  /approve <id>   - Sign-off a pending request\n"
        "  /telemetry      - Stream live SCADA sensor readings\n"
        "  /clear          - Clear screen\n"
        "  /exit           - Exit session[/dim]\n"
    )

    current_image = None

    while True:
        try:
            prompt_str = f"[bold cyan]MRPL-Operator (WS:{workspace_id})>[/bold cyan] "
            user_input = Prompt.ask(prompt_str).strip()

            if not user_input:
                continue

            if user_input.lower() in ["/exit", "exit", "quit"]:
                console.print("[yellow]Exiting operator session. Goodbye![/yellow]")
                break

            elif user_input.lower() == "/clear":
                os.system("cls" if os.name == "nt" else "clear")
                print_banner()
                continue

            elif user_input.startswith("/image"):
                parts = user_input.split(maxsplit=1)
                if len(parts) > 1:
                    img_p = Path(parts[1].strip("'\""))
                    if img_p.exists():
                        current_image = str(img_p)
                        console.print(f"[bold green][OK] Attached image for inspection: {current_image}[/bold green]")
                    else:
                        console.print(f"[bold red]File not found: {parts[1]}[/bold red]")
                else:
                    current_image = None
                    console.print("[dim]Cleared attached image.[/dim]")
                continue

            elif user_input.lower() == "/status":
                system_status()
                continue

            elif user_input.lower() == "/approvals":
                list_approvals()
                continue

            elif user_input.startswith("/approve"):
                parts = user_input.split()
                if len(parts) > 1 and parts[1].isdigit():
                    approve_action(int(parts[1]))
                else:
                    console.print("[yellow]Usage: /approve <request_id>[/yellow]")
                continue

            elif user_input.lower() == "/telemetry":
                telemetry_stream()
                continue

            # Standard prompt execution
            async def _execute():
                with console.status("[bold green]Agent reasoning...[/bold green]", spinner="dots"):
                    resp = await execute_agent_run(
                        workspace_id=workspace_id,
                        agent_id=agent_id,
                        input_text=user_input,
                        input_image_path=current_image,
                    )

                if resp.status == "paused":
                    console.print(
                        f"\n[bold red][HITL GATE] HITL PAUSE:[/bold red] {resp.result_text}\n"
                        f"[yellow]To approve, type:[/yellow] `/approve <req_id>` (run `/approvals` to inspect)"
                    )
                else:
                    console.print(f"\n[bold green]CogniShift Assistant:[/bold green]\n{resp.result_text}\n")

            run_async(_execute())
            current_image = None  # Reset image after use

        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Session interrupted. Goodbye![/yellow]")
            break


@app.callback(invoke_without_command=True)
def default_callback(ctx: typer.Context):
    """Default action when running `cognishift` without arguments: starts interactive chat."""
    if ctx.invoked_subcommand is None:
        interactive_chat()


def main():
    app()


if __name__ == "__main__":
    main()
