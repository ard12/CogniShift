"""Bounded Multi-Step Planner and Resumable Plan State Machine for CogniShift."""
import json
import logging
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

StepStatus = Literal[
    "pending",
    "running",
    "waiting_for_approval",
    "completed",
    "failed",
    "blocked"
]


class PlanStep(BaseModel):
    """An individual atomic step in an agent's reasoning plan."""
    id: int
    description: str
    status: StepStatus = "pending"
    tool_name: Optional[str] = None
    tool_parameters: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0


class AgentPlan(BaseModel):
    """Structured plan tracking progress through a bounded multi-step reasoning task."""
    goal: str
    current_step_index: int = 0
    max_steps: int = 10
    steps: List[PlanStep] = Field(default_factory=list)
    final_synthesis: Optional[str] = None

    def get_current_step(self) -> Optional[PlanStep]:
        """Return the active step or None if completed."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def advance_to_next_step(self) -> bool:
        """Advance pointer to next step. Returns True if there are more steps."""
        self.current_step_index += 1
        return self.current_step_index < len(self.steps)

    def is_finished(self) -> bool:
        """Returns True if all steps are completed or max_steps reached."""
        if self.current_step_index >= len(self.steps) or self.current_step_index >= self.max_steps:
            return True
        return all(s.status in ["completed", "blocked", "failed"] for s in self.steps)


def create_initial_plan(goal: str, task_type: str = "general_reasoning") -> AgentPlan:
    """
    Constructs an initial structured plan based on the classified task type.
    Bounded strictly to <= 10 steps.
    """
    steps = []
    
    if task_type == "coding":
        steps = [
            PlanStep(id=1, description="Inspect task requirements and stage workspace input files"),
            PlanStep(id=2, description="Write autonomous Python solution script"),
            PlanStep(id=3, description="Execute script in isolated sandbox and verify returncode == 0"),
            PlanStep(id=4, description="Validate output artifacts and synthesize summary")
        ]
    elif task_type == "vision_inspection":
        steps = [
            PlanStep(id=1, description="Rasterize visual artifact and extract telemetry readings via local VLM"),
            PlanStep(id=2, description="Retrieve relevant equipment specifications from knowledge base"),
            PlanStep(id=3, description="Cross-reference sensor readings against safe operating envelope"),
            PlanStep(id=4, description="Synthesize findings and generate engineering recommendation")
        ]
    elif task_type == "conversational":
        steps = [
            PlanStep(id=1, description="Synthesize direct conversational answer addressing user query")
        ]
    elif task_type == "document_analysis":
        steps = [
            PlanStep(id=1, description="Retrieve relevant SOP and OISD standards via RAG vector search"),
            PlanStep(id=2, description="Query plant topology graph for connected equipment and interlocks"),
            PlanStep(id=3, description="Evaluate operating limits and compliance status"),
            PlanStep(id=4, description="Synthesize formal deliverable with precise manual citations")
        ]
    else:
        steps = [
            PlanStep(id=1, description="Retrieve relevant domain context from knowledge base"),
            PlanStep(id=2, description="Formulate technical assessment and execute necessary diagnostics"),
            PlanStep(id=3, description="Synthesize final engineering response")
        ]

    return AgentPlan(goal=goal, current_step_index=0, max_steps=10, steps=steps)


def format_plan_for_prompt(plan: AgentPlan) -> str:
    """Render structured plan as a clean prompt section for the LLM."""
    lines = [
        f"=== STRUCTURED EXECUTION PLAN (Goal: {plan.goal}) ===",
        f"Current Step Index: {plan.current_step_index + 1}/{len(plan.steps)}",
        "Steps:"
    ]
    for step in plan.steps:
        status_badge = {
            "pending": "[ ] PENDING",
            "running": "[>] RUNNING",
            "waiting_for_approval": "[!] WAITING FOR SUPERVISOR APPROVAL",
            "completed": "[X] COMPLETED",
            "failed": "[-] FAILED",
            "blocked": "[#] BLOCKED"
        }.get(step.status, step.status)

        line = f"  {step.id}. {status_badge}: {step.description}"
        if step.observation:
            line += f" | Observation: {step.observation[:120]}..."
        if step.error_message:
            line += f" | Error: {step.error_message}"
        lines.append(line)
        
    lines.append("==================================================")
    return "\n".join(lines)


def serialize_plan(plan: AgentPlan) -> str:
    """Serialize plan to JSON string for database storage."""
    return plan.model_dump_json(indent=2)


def deserialize_plan(plan_json: Optional[str]) -> Optional[AgentPlan]:
    """Deserialize plan from JSON string."""
    if not plan_json:
        return None
    try:
        data = json.loads(plan_json)
        return AgentPlan.model_validate(data)
    except Exception as e:
        logger.error(f"Failed to deserialize agent plan: {e}")
        return None
