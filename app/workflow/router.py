from typing import Literal

from app.workflow.state import WorkflowState


def route_after_supervisor(
    state: WorkflowState,
) -> Literal["research", "coding", "analysis", "end"]:

    if state.get("status") == "cancelled":
        return "end"

    if state.get("error"):
        return "end"

    plan = state.get("plan")

    if not plan:
        return "end"

    agent = plan.get("agent")

    if agent == "research":
        return "research"

    if agent == "coding":
        return "coding"

    if agent == "analysis":
        return "analysis"

    return "end"


def route_after_agent(
    state: WorkflowState,
) -> Literal["tools", "reflection", "aggregator", "end"]:

    if state.get("status") == "cancelled":
        return "end"

    if state.get("error"):
        return "end"

    if state.get("tool_requests"):
        return "tools"

    if state.get("agent_result"):
        return "reflection"

    return "end"


def route_after_reflection(
    state: WorkflowState,
) -> Literal["research", "coding", "analysis", "aggregator", "end"]:

    if state.get("status") == "cancelled":
        return "end"

    if state.get("error"):
        return "end"

    decision = state.get("reflection_decision")

    if decision == "pass":
        return "aggregator"

    if decision == "retry":
        agent = state.get("selected_agent")

        if agent == "research":
            return "research"

        if agent == "coding":
            return "coding"

        if agent == "analysis":
            return "analysis"

    return "end"


def route_after_tools(
    state: WorkflowState,
) -> Literal["research", "coding", "analysis", "end"]:

    if state.get("status") == "cancelled":
        return "end"

    if state.get("error"):
        return "end"

    agent = state.get("selected_agent")

    if agent == "research":
        return "research"

    if agent == "coding":
        return "coding"

    if agent == "analysis":
        return "analysis"

    return "end"
