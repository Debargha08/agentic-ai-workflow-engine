from typing import Literal, TypedDict


AgentType = Literal["research", "coding", "analysis"]

WorkflowStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
]

ReflectionDecision = Literal["pass", "retry"]


class Plan(TypedDict):
    objective: str
    agent: AgentType
    steps: list[str]


class ToolRequest(TypedDict):
    name: str
    args: dict
    id: str


class ToolResult(TypedDict):
    name: str
    success: bool
    result: str
    error: str
    cancel_requested: bool
    id: str


class AttemptRecord(TypedDict):
    attempt: int
    agent: AgentType
    result: str
    reflection_decision: ReflectionDecision
    reflection_reason: str


class WorkflowState(TypedDict, total=False):
    # Core workflow state
    workflow_id: str
    task: str
    plan: Plan

    # Results
    result: str
    agent_result: str
    final_result: str

    # Tool execution
    tool_requests: list[ToolRequest]
    tool_results: list[ToolResult]
    tool_calls: list[dict]
    tool_round: int

    # Workflow status
    error: str
    cancel_requested: bool
    status: WorkflowStatus
    selected_agent: AgentType

    # Retry / reflection
    retry_count: int
    max_retries: int
    reflection_decision: ReflectionDecision
    reflection_reason: str
    attempt_history: list[AttemptRecord]
