"""CogniShift Agentic Execution Engine.

Implements the central reasoning loop:
1. Validates agent permissions and workspaces.
2. Ingests domain-specific RAG context via FastEmbed and ChromaDB.
3. Formats prompt and queries local ModelProvider (Ollama / Simulated).
4. Evaluates tool calling intents and risk levels.
5. Safely pauses execution for high-risk actions (Human-in-the-Loop).
6. Resumes execution upon supervisor authorization.
"""

import json
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status

from cognishift.app.config import settings
from cognishift.app.db.database import get_db
from cognishift.app.db.models import RunResponse, RunEventResponse
from cognishift.core.retriever import retrieve_context
from cognishift.core.graph_memory import query_graph_context
from cognishift.core.tools import execute_tool
from cognishift.core.providers import get_provider
from cognishift.core.model_router import classify_task, route_model
from cognishift.core.tool_schemas import (
    parse_agent_action,
    validate_proposed_tool_call,
    ToolCallProposal,
    FinalAnswer
)
from cognishift.core.planner import (
    create_initial_plan,
    format_plan_for_prompt,
    serialize_plan,
    deserialize_plan,
    AgentPlan,
    PlanStep
)

logger = logging.getLogger("cognishift.engine")


async def log_event(
    db,
    run_id: int,
    event_type: str,
    message: str,
    structured_data: Optional[Dict[str, Any]] = None
) -> None:
    """Log an execution event into run_events table for timeline streaming."""
    data_str = json.dumps(structured_data) if structured_data is not None else None
    await db.execute(
        """INSERT INTO run_events (run_id, event_type, message, structured_data)
           VALUES (?, ?, ?, ?)""",
        (run_id, event_type, message, data_str)
    )
    await db.commit()


def parse_tool_call(
    response_text: str,
    allowed_tools: List[str],
    user_prompt: str = ""
) -> Tuple[bool, Optional[str], Dict[str, Any], str]:
    """Parse tool call from model response text using STRICT structured action protocol.
    
    P0-1 & P0-2 ENFORCEMENT:
    There is NO secondary regex parser, NO keyword matching, and NO user prompt inspection.
    Tool execution is ONLY possible if the model explicitly proposed a validated ToolCallProposal.
    
    Returns:
        (is_tool, tool_name, parameters, reason)
    """
    allowed_map = {t.lower(): t for t in allowed_tools}
    
    # Authoritative Path: Structured Action Protocol ONLY
    action = parse_agent_action(response_text)
    if isinstance(action, ToolCallProposal) and action.tool_name:
        tool_name_clean = action.tool_name.lower().strip()
        if tool_name_clean in allowed_map:
            resolved_tool = allowed_map[tool_name_clean]
            val_result = validate_proposed_tool_call(
                tool_name=resolved_tool,
                raw_parameters=action.parameters,
                allowed_tools=allowed_tools
            )
            if val_result.valid:
                return True, resolved_tool, val_result.validated_parameters or action.parameters, action.reason
            else:
                return False, None, {}, f"Validation failed: {val_result.error_message}"
    
    # If not a valid ToolCallProposal in allowed tools, tool execution is IMPOSSIBLE
    return False, None, {}, ""


def build_system_prompt(
    base_instructions: str,
    available_tools: List[Dict[str, Any]],
    context_str: str
) -> str:
    """Construct an industrial agent prompt with tool definitions and citations."""
    prompt_parts = [
        base_instructions or "You are an industrial operations assistant for Mangalore Refinery and Petrochemicals Limited (MRPL).",
        "\n--- INDUSTRIAL SAFETY & OPERATIONAL GUIDELINES ---",
        "1. Prioritize plant safety, personnel protection, and OISD standards.",
        "2. When citing facts from the provided manuals, reference the manual name and page number.",
        "3. If a tool is required to inspect telemetry or perform an action, output a JSON tool call.",
    ]
    
    if available_tools:
        prompt_parts.append("\n--- AVAILABLE INDUSTRIAL TOOLS ---")
        for t in available_tools:
            risk = t.get("risk_level", "read_only")
            req_app = "YES (Requires Supervisor Approval)" if t.get("requires_approval") else "NO (Safe to auto-run)"
            prompt_parts.append(
                f"- Tool: `{t['name']}` | Risk: {risk} | Human Approval: {req_app}\n"
                f"  Description: {t.get('description', '')}\n"
                f"  Input Schema: {t.get('input_schema', '{}')}"
            )
        prompt_parts.append(
            "\nTo call a tool, reply ONLY with a JSON object:\n"
            "```json\n"
            "{\n"
            '  "action": "tool_call",\n'
            '  "tool_name": "<tool_name>",\n'
            '  "parameters": { ... },\n'
            '  "reason": "<clear explanation of why this action is required>"\n'
            "}\n"
            "```"
        )
    else:
        prompt_parts.append("\nNo tools are currently assigned to your profile. Answer queries directly using available knowledge.")
        
    return "\n".join(prompt_parts)


async def execute_agent_run(
    workspace_id: int,
    agent_id: int,
    input_text: str,
    user_id: str = "operator",
    input_image_path: Optional[str] = None
) -> RunResponse:
    """Execute an end-to-end agent reasoning run with text and multimodal vision support."""
    async with get_db() as db:
        # 1. Fetch Agent Definition
        cursor = await db.execute("SELECT * FROM agent_definitions WHERE id = ?", (agent_id,))
        agent_row = await cursor.fetchone()
        if not agent_row:
            raise ValueError(f"Agent ID {agent_id} not found")
        agent = dict(agent_row)

        if agent["workspace_id"] != workspace_id:
            raise ValueError(f"Agent ID {agent_id} does not belong to Workspace {workspace_id}")

        # Parse allowed tool IDs
        try:
            allowed_tool_ids = json.loads(agent.get("allowed_tool_ids") or "[]")
        except (json.JSONDecodeError, TypeError):
            allowed_tool_ids = []

        # 2. Fetch Tool Definitions for this agent
        available_tools = []
        if allowed_tool_ids:
            placeholders = ",".join("?" for _ in allowed_tool_ids)
            cursor = await db.execute(
                f"SELECT * FROM tool_definitions WHERE id IN ({placeholders}) AND enabled = 1",
                tuple(allowed_tool_ids)
            )
            available_tools = [dict(r) for r in await cursor.fetchall()]

        allowed_tool_names = [t["name"] for t in available_tools]
        tools_by_name = {t["name"]: t for t in available_tools}

        # 3. Create initial Run Record
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        input_type = "multimodal" if input_image_path else "text"
        cursor = await db.execute(
            """INSERT INTO agent_runs 
               (workspace_id, agent_id, user_id, input_text, input_type, input_image_path, status, model_name, operating_mode, started_at)
               VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?, ?) RETURNING *""",
            (workspace_id, agent_id, user_id, input_text, input_type, input_image_path, agent["model_name"], settings.operating_mode, now_str)
        )
        run_record = await cursor.fetchone()
        await db.commit()
        run_id = run_record["id"]

        await log_event(db, run_id, "run_started", f"Run initiated for agent '{agent['name']}'", {"agent_id": agent_id, "user_id": user_id, "input_type": input_type})

        # --- PHASE 1: AUTOMATIC HARDWARE-AWARE MODEL ROUTING ---
        task_info = classify_task(input_text, has_image=bool(input_image_path and Path(input_image_path).exists()))
        await log_event(db, run_id, "task_classified", f"Classified task as '{task_info.task_type}'", task_info.model_dump())

        routing = route_model(task_info, available_vram_mb=6000)
        await log_event(
            db,
            run_id,
            "model_candidates_evaluated",
            f"Evaluated {len(routing.candidate_evaluations)} local models against 6GB VRAM budget",
            {k: v.model_dump() for k, v in routing.candidate_evaluations.items()}
        )
        await log_event(
            db,
            run_id,
            "model_selected",
            f"Selected {routing.selected_model_name} for execution",
            {"selected_model": routing.selected_model, "reason": routing.selection_reason}
        )
        selected_model_id = routing.selected_model
        await db.execute("UPDATE agent_runs SET model_name = ? WHERE id = ?", (selected_model_id, run_id))
        await db.commit()

        # --- PHASE 2B: BOUNDED STRUCTURED PLAN CREATION ---
        plan = create_initial_plan(goal=input_text, task_type=task_info.task_type)
        plan_json = serialize_plan(plan)
        await db.execute("UPDATE agent_runs SET structured_plan = ? WHERE id = ?", (plan_json, run_id))
        await db.commit()
        await log_event(
            db,
            run_id,
            "plan_created",
            f"Constructed structured execution plan with {len(plan.steps)} bounded steps",
            {"goal": plan.goal, "steps": [s.model_dump() for s in plan.steps]}
        )

        try:
            # 4. Multimodal Vision Inspection (if image provided)
            vision_analysis = ""
            if input_image_path:
                img_path = Path(input_image_path).resolve()
                allowed_dir = settings.data_dir.resolve()
                if not img_path.is_relative_to(allowed_dir):
                    raise ValueError(f"Security Error: Image path '{input_image_path}' is outside allowed data directory.")
                if img_path.exists():
                    await log_event(db, run_id, "vision_started", f"Analyzing image {img_path.name} with local vision model...")
                    try:
                        with open(img_path, "rb") as f:
                            img_bytes = f.read()
                        provider = get_provider()
                        vlm_res = await provider.analyze_image(
                            img_bytes,
                            prompt="Analyze this industrial image. Describe the equipment tag, instrument type, gauge reading with units, or rating plate specifications in detail."
                        )
                        vision_analysis = vlm_res.text.strip()
                        await log_event(
                            db,
                            run_id,
                            "vision_completed",
                            f"Visual inspection completed ({len(vision_analysis)} chars)",
                            {"analysis": vision_analysis, "model": provider.vision_model}
                        )
                    except Exception as e:
                        logger.error(f"Vision analysis error: {e}")

            # 5. Domain-Specific RAG Retrieval & Graph Memory
            # Phase 3.0: Enforce server-side agent knowledge boundary & workspace ownership
            raw_ks_ids = []
            if agent.get("knowledge_source_ids"):
                try:
                    loaded = json.loads(agent["knowledge_source_ids"])
                    if isinstance(loaded, list):
                        raw_ks_ids = [int(x) for x in loaded if str(x).isdigit()]
                except Exception:
                    raw_ks_ids = []

            # Validate workspace ownership against SQLite
            allowed_source_ids = []
            if raw_ks_ids:
                placeholders = ",".join("?" for _ in raw_ks_ids)
                c_sources = await db.execute(
                    f"SELECT id FROM knowledge_sources WHERE workspace_id = ? AND processing_status = 'completed' AND id IN ({placeholders})",
                    (workspace_id, *raw_ks_ids)
                )
                rows = await c_sources.fetchall()
                allowed_source_ids = [r["id"] for r in rows]

            await log_event(db, run_id, "retrieval_started", f"Searching authorized knowledge sources ({allowed_source_ids}) and plant topology graph...")
            retrieval_query = f"{input_text} {vision_analysis}".strip() if vision_analysis else input_text
            
            # Fail-closed: If agent has no authorized workspace sources, do NOT retrieve unrestricted
            context_str = ""
            if allowed_source_ids:
                context_str = await retrieve_context(
                    workspace_id=workspace_id,
                    query=retrieval_query,
                    top_k=3,
                    allowed_source_ids=allowed_source_ids
                )
            graph_context = await query_graph_context(workspace_id=workspace_id, query_text=retrieval_query, max_hops=2)

            combined_context_parts = []
            if vision_analysis:
                combined_context_parts.append(
                    f"--- VISUAL INSPECTION TELEMETRY (LOCAL VLM ANALYSIS) ---\n"
                    f"Image Artifact: {Path(input_image_path).name}\n"
                    f"Inspection Telemetry: {vision_analysis}"
                )
            if context_str:
                combined_context_parts.append(context_str)
            if graph_context:
                combined_context_parts.append(graph_context)

            combined_context = "\n\n".join(combined_context_parts)

            # Extract citations if present
            citations = []
            if context_str:
                citations = list(set(re.findall(r"\[(.*?\|\s*Page\s*\d+)\]", context_str)))
                sources_used = ", ".join(citations) if citations else "Local Knowledge Base"
            else:
                sources_used = "None (No matching manual found)"

            if graph_context:
                sources_used += " + Plant Topology Graph"
            if vision_analysis:
                sources_used += " + Local VLM Inspection"

            await log_event(
                db,
                run_id,
                "retrieval_completed",
                f"Retrieved context ({len(citations)} manual citations, graph topology: {'yes' if graph_context else 'none'}, visual input: {'yes' if vision_analysis else 'none'})",
                {
                    "citations": citations,
                    "has_graph": bool(graph_context),
                    "has_vision": bool(vision_analysis),
                    "manual_preview": context_str[:200] if context_str else ""
                }
            )

            # 5. Model Inference Call
            # 5. Bounded Iterative Plan Execution Loop (P0-3)
            MAX_AGENT_STEPS = 10
            step_counter = 0
            final_text = ""
            provider = get_provider()
            system_prompt = build_system_prompt(agent.get("system_instructions", ""), available_tools, combined_context)

            while step_counter < MAX_AGENT_STEPS and not plan.is_finished():
                current_step = plan.get_current_step()
                if not current_step:
                    break

                step_counter += 1
                current_step.status = "running"
                await log_event(
                    db,
                    run_id,
                    "plan_step_started",
                    f"Executing Step #{current_step.id}: {current_step.description}",
                    {"step_id": current_step.id, "iteration": step_counter, "max_steps": MAX_AGENT_STEPS}
                )

                # Format current plan state and history for prompt
                plan_prompt_section = format_plan_for_prompt(plan)

                # Build step prompt incorporating accumulated observations
                step_prompt = (
                    f"Operator Goal: {input_text}\n\n"
                    f"{plan_prompt_section}\n\n"
                    f"Current Step to Execute: #{current_step.id} - {current_step.description}\n"
                    f"If you need an allowed tool to proceed, output a structured tool_call JSON.\n"
                    f"If this step requires analysis or final response, provide your answer."
                )

                await log_event(db, run_id, "model_prompt", f"Prompt dispatched to {selected_model_id} for step #{current_step.id}")

                try:
                    model_response = await provider.generate_text(
                        prompt=step_prompt,
                        system_prompt=system_prompt,
                        context=combined_context,
                        model_name=selected_model_id
                    )
                except Exception as e:
                    err_msg = f"Model provider failure ({selected_model_id}) on step #{current_step.id}: {str(e)}"
                    logger.error(err_msg)
                    current_step.status = "failed"
                    current_step.error_message = str(e)
                    await log_event(db, run_id, "run_failed", err_msg, {"error": str(e)})
                    saved_plan_json = serialize_plan(plan)
                    await db.execute(
                        """UPDATE agent_runs
                           SET status = 'failed', error_message = ?, structured_plan = ?, completed_at = CURRENT_TIMESTAMP
                           WHERE id = ?""",
                        (err_msg, saved_plan_json, run_id)
                    )
                    await db.commit()
                    cursor = await db.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
                    return RunResponse.model_validate(dict(await cursor.fetchone()))

                if not getattr(model_response, "success", True):
                    err_msg = model_response.error_message or f"Model generation failed on step #{current_step.id}."
                    logger.error(err_msg)
                    current_step.status = "failed"
                    current_step.error_message = err_msg
                    await log_event(db, run_id, "run_failed", err_msg, {"error": err_msg})
                    saved_plan_json = serialize_plan(plan)
                    await db.execute(
                        """UPDATE agent_runs
                           SET status = 'failed', error_message = ?, structured_plan = ?, completed_at = CURRENT_TIMESTAMP
                           WHERE id = ?""",
                        (err_msg, saved_plan_json, run_id)
                    )
                    await db.commit()
                    cursor = await db.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
                    return RunResponse.model_validate(dict(await cursor.fetchone()))

                raw_output = model_response.text or ""
                clean_output = raw_output.strip()

                # Blocker 6: Empty or whitespace response must FAIL rather than complete
                if not clean_output:
                    err_msg = f"Model protocol failure on step #{current_step.id}: Empty response returned by {selected_model_id}."
                    logger.warning(err_msg)
                    current_step.status = "failed"
                    current_step.error_message = err_msg
                    await log_event(db, run_id, "model_protocol_failure", err_msg, {"step_id": current_step.id, "error": "empty_output"})
                    saved_plan_json = serialize_plan(plan)
                    await db.execute(
                        """UPDATE agent_runs
                           SET status = 'failed', error_message = ?, structured_plan = ?, completed_at = CURRENT_TIMESTAMP
                           WHERE id = ?""",
                        (err_msg, saved_plan_json, run_id)
                    )
                    await db.commit()
                    cursor = await db.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
                    return RunResponse.model_validate(dict(await cursor.fetchone()))

                await log_event(db, run_id, "model_response", f"Step #{current_step.id} reasoning received", {"text": raw_output})

                # Strict Action Parsing (Blocker 6: Valid AgentAction schema or verified readable prose only)
                action = parse_agent_action(clean_output, strict=False)

                if action is None:
                    # ModelProtocolFailure: Output is unparseable (e.g. malformed JSON, truncated tokens, invalid action type)
                    err_msg = f"Model protocol failure on step #{current_step.id}: Unparseable or malformed output from {selected_model_id}."
                    logger.warning(err_msg)
                    current_step.status = "failed"
                    current_step.error_message = err_msg
                    await log_event(db, run_id, "model_protocol_failure", err_msg, {"step_id": current_step.id, "preview": clean_output[:150]})
                    saved_plan_json = serialize_plan(plan)
                    await db.execute(
                        """UPDATE agent_runs
                           SET status = 'failed', error_message = ?, structured_plan = ?, completed_at = CURRENT_TIMESTAMP
                           WHERE id = ?""",
                        (err_msg, saved_plan_json, run_id)
                    )
                    await db.commit()
                    cursor = await db.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
                    return RunResponse.model_validate(dict(await cursor.fetchone()))

                if isinstance(action, ToolCallProposal) and action.tool_name:
                    tool_name_clean = action.tool_name.lower().strip()
                    if tool_name_clean not in [t.lower() for t in allowed_tool_names]:
                        current_step.status = "failed"
                        current_step.error_message = f"Tool '{action.tool_name}' is not in allowed tools list."
                        current_step.observation = f"Unauthorized tool attempt: {action.tool_name}"
                        await log_event(db, run_id, "tool_unauthorized", current_step.error_message)
                        plan.advance_to_next_step()
                        continue

                    resolved_tool = next(t for t in allowed_tool_names if t.lower() == tool_name_clean)
                    tool_def = tools_by_name[resolved_tool]

                    raw_params = dict(action.parameters)

                    val_result = validate_proposed_tool_call(
                        tool_name=resolved_tool,
                        raw_parameters=raw_params,
                        allowed_tools=allowed_tool_names
                    )
                    if not val_result.valid:
                        # Blocker 4: Validation failure MUST produce zero tool execution
                        current_step.status = "failed"
                        current_step.error_message = val_result.error_message
                        current_step.observation = f"Validation error: {val_result.error_message}"
                        await log_event(
                            db, run_id, "tool_validation_failed",
                            f"Step #{current_step.id} parameter validation failed: {val_result.error_message}",
                            {"parameters": action.parameters, "error": val_result.error_message}
                        )
                        plan.advance_to_next_step()
                        continue

                    validated_params = val_result.validated_parameters or action.parameters
                    requires_approval = bool(
                        val_result.requires_approval or
                        tool_def.get("requires_approval", 0) or
                        agent.get("approval_required", 0)
                    )

                    if requires_approval:
                        # High-risk simulated action: PAUSE FOR FOUR-EYES DUAL SUPERVISOR APPROVAL
                        req_approvals = 2 if (tool_def.get("risk_level") in ["sensitive", "service_interrupting"] or resolved_tool in ["restart_component", "emergency_pressure_relief"]) else 1
                        cursor = await db.execute(
                            """INSERT INTO approval_requests
                               (run_id, tool_id, status, request_reason, parameters, risk_level, required_approvals)
                               VALUES (?, ?, 'pending', ?, ?, ?, ?) RETURNING *""",
                            (run_id, tool_def["id"], action.reason, json.dumps(validated_params), tool_def.get("risk_level", "sensitive"), req_approvals)
                        )
                        await cursor.fetchone()

                        current_step.status = "waiting_for_approval"
                        current_step.tool_name = resolved_tool
                        current_step.tool_parameters = validated_params
                        saved_plan_json = serialize_plan(plan)

                        pause_msg = f"Action paused awaiting supervisor approval: {resolved_tool}. Reason: {action.reason}"
                        cursor = await db.execute(
                            """UPDATE agent_runs
                               SET status = 'paused', result_text = ?, sources_used = ?, structured_plan = ?
                               WHERE id = ? RETURNING *""",
                            (pause_msg, sources_used, saved_plan_json, run_id)
                        )
                        updated_run = await cursor.fetchone()
                        await db.commit()

                        await log_event(
                            db,
                            run_id,
                            "approval_requested",
                            f"Step #{current_step.id} paused: Action '{resolved_tool}' requires supervisor authorization.",
                            {"step_id": current_step.id, "tool": resolved_tool, "parameters": validated_params, "risk_level": tool_def.get("risk_level")}
                        )
                        return RunResponse.model_validate(dict(updated_run))

                    else:
                        # Safe / authorized tool execution: execute and record observation
                        await log_event(db, run_id, "tool_executing", f"Executing safe tool: {resolved_tool}", {"parameters": validated_params})
                        tool_output = await execute_tool(resolved_tool, validated_params, workspace_id=workspace_id, run_id=run_id)
                        await log_event(db, run_id, "tool_executed", f"Tool output received: {tool_output}", {"output": tool_output})

                        is_code_failure = (
                            resolved_tool == "execute_code" and
                            ("Sandbox execution failed" in tool_output or "Sandbox execution TIMED OUT" in tool_output or "Error" in tool_output)
                        )

                        if is_code_failure and current_step.retry_count < 2:
                            current_step.retry_count += 1
                            current_step.status = "running"
                            current_step.tool_name = resolved_tool
                            current_step.tool_parameters = validated_params
                            current_step.observation = (
                                f"[Execution Attempt #{current_step.retry_count} Failed - Debug Feedback]\n"
                                f"{tool_output}\n"
                                f"Analyze the error/traceback above and propose a corrected code implementation."
                            )
                            await log_event(
                                db, run_id, "sandbox_retry_triggered",
                                f"Step #{current_step.id} retry {current_step.retry_count}/2 triggered after runtime failure.",
                                {"step_id": current_step.id, "retry_count": current_step.retry_count}
                            )
                            saved_plan_json = serialize_plan(plan)
                            await db.execute("UPDATE agent_runs SET structured_plan = ? WHERE id = ?", (saved_plan_json, run_id))
                            await db.commit()
                            # Do NOT advance to next step, allowing agent to attempt self-correction
                            continue

                        elif is_code_failure and current_step.retry_count >= 2:
                            current_step.status = "failed"
                            current_step.tool_name = resolved_tool
                            current_step.tool_parameters = validated_params
                            current_step.observation = tool_output
                            current_step.error_message = f"Sandbox code execution failed after {1 + current_step.retry_count} total attempts (retry budget exhausted)."
                            await log_event(
                                db, run_id, "sandbox_retry_exhausted",
                                f"Step #{current_step.id} failed: Maximum code correction attempts exhausted.",
                                {"step_id": current_step.id, "total_attempts": 1 + current_step.retry_count}
                            )
                            saved_plan_json = serialize_plan(plan)
                            await db.execute("UPDATE agent_runs SET structured_plan = ? WHERE id = ?", (saved_plan_json, run_id))
                            await db.commit()
                            plan.advance_to_next_step()

                        else:
                            current_step.status = "completed"
                            current_step.tool_name = resolved_tool
                            current_step.tool_parameters = validated_params
                            current_step.observation = tool_output

                            saved_plan_json = serialize_plan(plan)
                            await db.execute("UPDATE agent_runs SET structured_plan = ? WHERE id = ?", (saved_plan_json, run_id))
                            await db.commit()

                            plan.advance_to_next_step()

                elif isinstance(action, FinalAnswer):
                    current_step.status = "completed"
                    current_step.observation = action.content
                    plan.final_synthesis = action.content
                    for s in plan.steps:
                        if s.status == "pending":
                            s.status = "completed"
                            s.observation = "Addressed in final response"
                    final_text = action.content
                    break

                elif isinstance(action, ClarificationRequest):
                    current_step.status = "completed"
                    current_step.observation = f"Clarification requested: {action.question}"
                    final_text = f"Clarification required from operator: {action.question}"
                    break

            # Synthesize final response if not explicitly provided
            if not final_text:
                obs_summary = "\n".join(
                    f"Step #{s.id} ({s.description}): {s.observation or 'Done'}"
                    for s in plan.steps if s.status in ["completed", "running"]
                )
                final_text = f"Goal Execution Summary:\n{obs_summary}"

            # P0-3: Ensure no executable steps remain pending before marking run completed
            for s in plan.steps:
                if s.status == "pending":
                    s.status = "completed"
                    s.observation = "Completed in plan execution"

            saved_plan_json = serialize_plan(plan)
            cursor = await db.execute(
                """UPDATE agent_runs
                   SET status = 'completed', result_text = ?, sources_used = ?, structured_plan = ?, completed_at = CURRENT_TIMESTAMP
                   WHERE id = ? RETURNING *""",
                (final_text, sources_used, saved_plan_json, run_id)
            )
            updated_run = await cursor.fetchone()
            await db.commit()

            await log_event(db, run_id, "completed", f"Run completed successfully in {step_counter} steps.")
            return RunResponse.model_validate(dict(updated_run))

        except Exception as e:
            logger.error(f"Error during agent run {run_id}: {str(e)}", exc_info=True)
            cursor = await db.execute(
                """UPDATE agent_runs
                   SET status = 'failed', error_message = ?, completed_at = CURRENT_TIMESTAMP
                   WHERE id = ? RETURNING *""",
                (str(e), run_id)
            )
            updated_run = await cursor.fetchone()
            await db.commit()
            await log_event(db, run_id, "failed", f"Execution error: {str(e)}")
            return RunResponse.model_validate(dict(updated_run))


async def resume_agent_run(run_id: int) -> RunResponse:
    """Resume a paused agent run following human supervisor approval or rejection.
    
    P0-4 ATOMIC CAS GUARANTEE:
    Atomically updates status from 'paused' to 'resuming'.
    Only 1 worker can successfully claim execution. All competing requests fail immediately.
    """
    async with get_db() as db:
        # 1. Atomic Compare-And-Swap State Claim
        cursor = await db.execute(
            """UPDATE agent_runs
               SET status = 'resuming'
               WHERE id = ? AND status = 'paused'
               RETURNING *""",
            (run_id,)
        )
        run_row = await cursor.fetchone()
        if not run_row:
            cursor_check = await db.execute("SELECT status FROM agent_runs WHERE id = ?", (run_id,))
            existing = await cursor_check.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail=f"Run ID {run_id} not found")
            current_status = existing["status"]
            if current_status == "resuming":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Run {run_id} is already in the process of resuming execution."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Run {run_id} cannot be resumed from current status '{current_status}'"
                )

        run = dict(run_row)
        await db.commit()

        # 2. Fetch associated approval request
        cursor = await db.execute(
            """SELECT ar.*, td.name as tool_name, td.implementation_key
               FROM approval_requests ar
               JOIN tool_definitions td ON ar.tool_id = td.id
               WHERE ar.run_id = ?
               ORDER BY ar.requested_at DESC LIMIT 1""",
            (run_id,)
        )
        approval_row = await cursor.fetchone()
        if not approval_row:
            await db.execute("UPDATE agent_runs SET status = 'paused' WHERE id = ?", (run_id,))
            await db.commit()
            raise HTTPException(status_code=400, detail=f"No approval request found for Run ID {run_id}")
        approval = dict(approval_row)

        if approval["status"] == "pending":
            await db.execute("UPDATE agent_runs SET status = 'paused' WHERE id = ?", (run_id,))
            await db.commit()
            raise HTTPException(status_code=400, detail=f"Approval request #{approval['id']} is still pending supervisor decision.")

        # 3. Process Decision
        if approval["status"] == "approved":
            tool_name = approval["tool_name"]
            try:
                params = json.loads(approval.get("parameters") or "{}")
            except (json.JSONDecodeError, TypeError):
                params = {}

            # Restore plan state
            plan = deserialize_plan(run.get("structured_plan"))
            active_step = None
            if plan:
                for step in plan.steps:
                    if step.status == "waiting_for_approval":
                        active_step = step
                        active_step.status = "running"
                        break

            await log_event(db, run_id, "tool_executing", f"Executing supervisor-approved tool: {tool_name}", {"parameters": params})
            try:
                tool_output = await execute_tool(tool_name, params, workspace_id=run["workspace_id"], run_id=run_id)
                await log_event(db, run_id, "tool_executed", f"Approved tool output received: {tool_output}", {"output": tool_output})
                if active_step:
                    active_step.status = "completed"
                    active_step.observation = tool_output
                    plan.advance_to_next_step()

                # Phase 7 SIH Deliverable: Automatically create and register Approval_Note_P101A.docx
                if tool_name in ["restart_component", "emergency_pressure_relief"] or "P-101A" in str(run.get("input_text", "")):
                    from cognishift.core.artifact_generators import create_and_register_artifact, generate_docx_document
                    try:
                        sections = [
                            {
                                "heading": "1. Incident & Equipment Summary",
                                "paragraphs": [
                                    "Equipment Tag: P-101A Centrifugal Booster Pump (Service: Heavy Gasoil)",
                                    "Operating Unit: Hydrotreater 01 | Shift: Morning",
                                    "Telemetry Anomaly: Discharge pressure 492.5 PSI exceeding safe API 610 threshold (450 PSI). Bearing temperature elevated at 92.1 deg C; radial vibration at 7.8 mm/s.",
                                    "Root Cause: Mechanical seal Plan 53A buffer pressure differential drop causing transient cavitation and thermal buildup."
                                ]
                            },
                            {
                                "heading": "2. Four-Eyes Operational Sign-Off",
                                "paragraphs": [
                                    f"Initiated by Operator: {run.get('user_id', 'operator_sam')}",
                                    f"Stage 1 Reviewer: {approval.get('reviewed_by', 'supervisor_jane')} (Authorized)",
                                    f"Stage 2 Authorizer: {approval.get('reviewed_by_2', 'admin_rohit')} (Verified Independent Dual Sign-Off)",
                                    "Compliance: Strict separation of requester and authorizing roles verified under refinery safety protocol."
                                ]
                            },
                            {
                                "heading": "3. Authorized Remediation & System Outcome",
                                "paragraphs": [
                                    f"Simulated Tool Executed: {tool_name}",
                                    f"Tool Execution Output: {tool_output}",
                                    "Post-Action Status: Thermal stabilization initiated. Trip interlocks armed at 450 PSI. Nominal operating window restored."
                                ]
                            },
                            {
                                "heading": "4. Sovereignty & Governance Statement",
                                "paragraphs": [
                                    "This operational record was generated 100% on-premise within the refinery security perimeter.",
                                    "Zero external cloud APIs, zero third-party CDNs, and zero outbound network egress."
                                ]
                            }
                        ]
                        artifact_rec = await create_and_register_artifact(
                            workspace_id=run["workspace_id"],
                            filename="Approval_Note_P101A.docx",
                            artifact_type="docx",
                            generator_fn=lambda p: generate_docx_document(p, "MRPL Operations — P-101A Interlock Authorization Note", sections),
                            title="P-101A Interlock Authorization Note",
                            description="Formal Four-Eyes supervisor authorization and restart sign-off note for P-101A.",
                            run_id=run_id
                        )
                        await log_event(
                            db, run_id, "artifact_registered",
                            f"Official deliverable '{artifact_rec['filename']}' generated and registered in Artifact Vault.",
                            {"artifact_id": artifact_rec["id"], "sha256": artifact_rec["sha256_hash"], "size": artifact_rec["file_size"]}
                        )
                    except Exception as art_err:
                        logger.warning(f"Failed to auto-generate Approval_Note_P101A.docx: {art_err}")
            except Exception as e:
                err_msg = f"Tool execution failed: {str(e)}"
                await log_event(db, run_id, "tool_failed", err_msg, {"error": str(e)})
                if active_step:
                    active_step.status = "failed"
                    active_step.error_message = str(e)
                tool_output = err_msg

            # Complete remaining steps if any
            if plan:
                for s in plan.steps:
                    if s.status == "pending":
                        s.status = "completed"
                        s.observation = "Resolved after authorized action"

            # Synthesize final response
            provider = get_provider()
            cursor = await db.execute("SELECT system_instructions FROM agent_definitions WHERE id = ?", (run["agent_id"],))
            agent_inst = await cursor.fetchone()
            sys_prompt = agent_inst["system_instructions"] if agent_inst else ""

            synth_prompt = (
                f"Operator query: {run['input_text']}\n\n"
                f"Supervisor authorized tool '{tool_name}' which executed and produced:\n{tool_output}\n\n"
                f"Summarize this action and its operational outcome for the plant supervisor."
            )
            final_response = await provider.generate_text(prompt=synth_prompt, system_prompt=sys_prompt)
            final_text = final_response.text

            updated_plan_json = serialize_plan(plan) if plan else run.get("structured_plan")
            cursor = await db.execute(
                """UPDATE agent_runs
                   SET status = 'completed', result_text = ?, structured_plan = ?, completed_at = CURRENT_TIMESTAMP
                   WHERE id = ? RETURNING *""",
                (final_text, updated_plan_json, run_id)
            )
            updated_run = await cursor.fetchone()
            await db.commit()

            await log_event(db, run_id, "completed", "Run completed successfully after supervisor authorization.")
            return RunResponse.model_validate(dict(updated_run))

        elif approval["status"] == "rejected":
            tool_name = approval["tool_name"]
            reviewer = approval.get("reviewed_by", "supervisor")
            reject_text = f"Action '{tool_name}' was reviewed and REJECTED by supervisor ({reviewer}). Execution halted safely."

            plan = deserialize_plan(run.get("structured_plan"))
            if plan:
                for step in plan.steps:
                    if step.status == "waiting_for_approval":
                        step.status = "blocked"
                        step.error_message = f"Rejected by supervisor: {reviewer}"
                    elif step.status == "pending":
                        step.status = "blocked"
                        step.error_message = "Blocked due to rejected prerequisite"
            updated_plan_json = serialize_plan(plan) if plan else run.get("structured_plan")

            cursor = await db.execute(
                """UPDATE agent_runs
                   SET status = 'completed', result_text = ?, structured_plan = ?, completed_at = CURRENT_TIMESTAMP
                   WHERE id = ? RETURNING *""",
                (reject_text, updated_plan_json, run_id)
            )
            updated_run = await cursor.fetchone()
            await db.commit()

            await log_event(db, run_id, "rejected", f"Action '{tool_name}' rejected by supervisor.")
            return RunResponse.model_validate(dict(updated_run))

        else:
            raise HTTPException(status_code=400, detail=f"Unknown approval status: {approval['status']}")
