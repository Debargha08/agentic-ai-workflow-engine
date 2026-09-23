from app.workflow.state import WorkflowState


def aggregate_result(state: WorkflowState) -> WorkflowState:
    if state.get("error"):
        return state

    agent_result = state.get("agent_result", "").strip()

    if not agent_result:
        return {
            **state,
            "status": "failed",
            "error": "Agent produced no result.",
        }

    return {
        **state,
        "final_result": agent_result,
        "result": agent_result,
        "status": "completed",
    }
