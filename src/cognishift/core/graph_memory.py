"""Graph Memory Substrate for CogniShift.

Provides persistent, relational plant topology memory:
- Equipment to sensor relationships (e.g., Reactor-B -> HAS_SENSOR -> PT-101)
- Protection and safety links (e.g., Reactor-B -> PROTECTED_BY -> SV-402)
- Tool operational bindings (e.g., SV-402 -> ACTUATED_BY -> emergency_pressure_relief)
- Multi-hop traversal to supply structured topological context to the LLM alongside vector RAG.
"""

import json
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from cognishift.app.db.database import get_db


async def add_node(
    workspace_id: int,
    name: str,
    entity_type: str,
    properties: Optional[Dict[str, Any]] = None
) -> int:
    """Add or update an entity node in the workspace knowledge graph."""
    props_str = json.dumps(properties or {})
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO graph_nodes (workspace_id, name, entity_type, properties)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(workspace_id, name) DO UPDATE SET
                   entity_type = excluded.entity_type,
                   properties = excluded.properties
               RETURNING id""",
            (workspace_id, name.strip(), entity_type.strip().lower(), props_str)
        )
        row = await cursor.fetchone()
        await db.commit()
        return row["id"]


async def add_edge(
    workspace_id: int,
    source_name: str,
    relation_type: str,
    target_name: str,
    properties: Optional[Dict[str, Any]] = None
) -> int:
    """Add a directed relationship between two entities."""
    props_str = json.dumps(properties or {})
    async with get_db() as db:
        # Find or create source node
        cursor = await db.execute("SELECT id FROM graph_nodes WHERE workspace_id = ? AND name = ?", (workspace_id, source_name.strip()))
        src_row = await cursor.fetchone()
        if not src_row:
            src_id = await add_node(workspace_id, source_name.strip(), "entity")
        else:
            src_id = src_row["id"]

        # Find or create target node
        cursor = await db.execute("SELECT id FROM graph_nodes WHERE workspace_id = ? AND name = ?", (workspace_id, target_name.strip()))
        tgt_row = await cursor.fetchone()
        if not tgt_row:
            tgt_id = await add_node(workspace_id, target_name.strip(), "entity")
        else:
            tgt_id = tgt_row["id"]

        cursor = await db.execute(
            """INSERT INTO graph_edges (workspace_id, source_node_id, relation_type, target_node_id, properties)
               VALUES (?, ?, ?, ?, ?) RETURNING id""",
            (workspace_id, src_id, relation_type.strip().upper(), tgt_id, props_str)
        )
        row = await cursor.fetchone()
        await db.commit()
        return row["id"]


async def query_graph_context(workspace_id: int, query_text: str, max_hops: int = 2) -> str:
    """Traverse the knowledge graph starting from entities detected in query_text.
    
    Returns:
        Structured text describing the physical relationships between identified components.
    """
    async with get_db() as db:
        # 1. Fetch all nodes in this workspace
        cursor = await db.execute("SELECT id, name, entity_type, properties FROM graph_nodes WHERE workspace_id = ?", (workspace_id,))
        nodes = await cursor.fetchall()
        if not nodes:
            return ""

        query_lower = query_text.lower()
        matched_node_ids: Set[int] = set()
        node_map: Dict[int, Dict[str, Any]] = {}

        for n in nodes:
            d = dict(n)
            try:
                d["props"] = json.loads(d.get("properties") or "{}")
            except Exception:
                d["props"] = {}
            node_map[d["id"]] = d

            # Check if entity name or common alias appears in query
            name_lower = d["name"].lower()
            if name_lower in query_lower or name_lower.replace("-", " ") in query_lower or name_lower.replace("_", " ") in query_lower:
                matched_node_ids.add(d["id"])

        if not matched_node_ids:
            return ""

        # 2. Multi-hop traversal
        visited_nodes: Set[int] = set(matched_node_ids)
        frontier: Set[int] = set(matched_node_ids)
        collected_edges: List[Tuple[Dict[str, Any], str, Dict[str, Any], Dict[str, Any]]] = []

        for _ in range(max_hops):
            if not frontier:
                break
            placeholders = ",".join("?" for _ in frontier)
            cursor = await db.execute(
                f"""SELECT e.id, e.source_node_id, e.relation_type, e.target_node_id, e.properties
                   FROM graph_edges e
                   WHERE e.workspace_id = ? AND (e.source_node_id IN ({placeholders}) OR e.target_node_id IN ({placeholders}))""",
                (workspace_id, *frontier, *frontier)
            )
            edges = await cursor.fetchall()
            next_frontier: Set[int] = set()

            for edge in edges:
                src_id = edge["source_node_id"]
                tgt_id = edge["target_node_id"]
                rel = edge["relation_type"]
                try:
                    edge_props = json.loads(edge.get("properties") or "{}")
                except Exception:
                    edge_props = {}

                src_node = node_map.get(src_id)
                tgt_node = node_map.get(tgt_id)

                if src_node and tgt_node:
                    collected_edges.append((src_node, rel, tgt_node, edge_props))

                if src_id not in visited_nodes:
                    visited_nodes.add(src_id)
                    next_frontier.add(src_id)
                if tgt_id not in visited_nodes:
                    visited_nodes.add(tgt_id)
                    next_frontier.add(tgt_id)

            frontier = next_frontier

        if not collected_edges:
            # Fallback: Just return matched node descriptions
            lines = ["--- PLANT TOPOLOGY & GRAPH MEMORY ---"]
            for nid in matched_node_ids:
                n = node_map[nid]
                lines.append(f"• Component: {n['name']} (Type: {n['entity_type']}) | Specs: {json.dumps(n['props'])}")
            return "\n".join(lines)

        # 3. Format structured topological output
        lines = [
            "--- PLANT TOPOLOGY & GRAPH MEMORY (Physical Connections & Safety Links) ---"
        ]
        
        # Deduplicate edges
        seen_edges = set()
        for src, rel, tgt, props in collected_edges:
            edge_key = (src["id"], rel, tgt["id"])
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            src_info = f"{src['name']} [{src['entity_type']}]"
            tgt_info = f"{tgt['name']} [{tgt['entity_type']}]"
            extra = f" (Details: {props})" if props else ""
            lines.append(f"• {src_info} --({rel})--> {tgt_info}{extra}")

        # Add property specifics for involved components
        lines.append("\nComponent Specifications:")
        for nid in visited_nodes:
            n = node_map[nid]
            if n["props"]:
                prop_details = ", ".join(f"{k}: {v}" for k, v in n["props"].items())
                lines.append(f"  - {n['name']}: {prop_details}")

        return "\n".join(lines)


async def get_graph_export(workspace_id: int) -> Dict[str, Any]:
    """Export complete graph for UI visualization (nodes and links)."""
    async with get_db() as db:
        cursor = await db.execute("SELECT id, name, entity_type, properties FROM graph_nodes WHERE workspace_id = ?", (workspace_id,))
        nodes = []
        for r in await cursor.fetchall():
            d = dict(r)
            try:
                d["properties"] = json.loads(d["properties"])
            except Exception:
                d["properties"] = {}
            nodes.append(d)

        cursor = await db.execute(
            """SELECT e.id, e.source_node_id as source, e.target_node_id as target, e.relation_type as relation, e.properties
               FROM graph_edges e
               WHERE e.workspace_id = ?""",
            (workspace_id,)
        )
        links = []
        for r in await cursor.fetchall():
            d = dict(r)
            try:
                d["properties"] = json.loads(d["properties"])
            except Exception:
                d["properties"] = {}
            links.append(d)

        return {"nodes": nodes, "links": links}
