from typing import Any
import os

from langgraph.graph import END, START, StateGraph

from app.agents.analysis_agent import AnalysisAgent
from app.agents.coding_agent import CodingAgent
from app.agents.research_agent import ResearchAgent
from app.agents.reflection_agent import ReflectionAgent
from app.agents.supervisor import Supervisor
from app.database.repository import WorkflowRepository
from app.memory.manager import MemoryManager
from app.tools.executor import ToolExecutor
from app.workflow.aggregator import aggregate_result
from app.workflow.router import (
    route_after_agent,
    route_after_reflection,
    route_after_supervisor,
    route_after_tools,
)
from app.workflow.state import WorkflowState


WORKSPACE_ROOT = os.getenv("WORKSPACE_ROOT", ".")

supervisor = Supervisor()
research_agent = ResearchAgent()
coding_agent = CodingAgent()
analysis_agent = AnalysisAgent()
reflection_agent = ReflectionAgent()
tool_executor = ToolExecutor(WORKSPACE_ROOT)
memory = MemoryManager()
database = WorkflowRepository()


def persist(
    state: WorkflowState,
    event_type: str,
    message: str,
) -> None:
    workflow_id = state.get("workflow_id")

    if not workflow_id:
        return

    memory.save_state(
        workflow_id,
        state,
    )

    memory.record_event(
        workflow_id,
        {
            "type": event_type,
            "message": message,
        },
    )

    database.update_workflow(
        workflow_id,
        status=state.get("status"),
        selected_agent=state.get("selected_agent"),
        final_result=state.get("final_result"),
        error=state.get("error"),
        state=dict(state),
    )



def cancellation_guard(
    state: WorkflowState,
) -> WorkflowState | None:
    workflow_id = state.get("workflow_id")

    if not workflow_id:
        return None

    if not memory.is_cancel_requested(workflow_id):
        return None

    result = {
        **state,
        "status": "cancelled",
        "cancel_requested": True,
        "error": "Workflow cancelled.",
        "tool_requests": [],
    }

    memory.save_state(workflow_id, result)
    memory.record_event(
        workflow_id,
        {
            "type": "workflow_cancelled",
            "message": "Workflow cancelled before the next node executed.",
        },
    )

    database.update_workflow(
        workflow_id,
        status="cancelled",
        error="Workflow cancelled.",
        state=dict(result),
    )

    return result


def supervisor_node(state: WorkflowState) -> WorkflowState:
    cancelled = cancellation_guard(state)
    if cancelled is not None:
        return cancelled
    try:
        task = state.get("task", "").strip()

        if not task:
            result = {
                **state,
                "status": "failed",
                "error": "Task is required and cannot be empty.",
            }

            persist(
                result,
                "workflow_failed",
                "Task validation failed.",
            )

            return result

        plan = supervisor.create_plan(task)

        result = {
            **state,
            "task": task,
            "plan": plan,
            "selected_agent": plan["agent"],
            "status": "running",
            "error": "",
        }

        persist(
            result,
            "supervisor_completed",
            f"Selected agent: {plan['agent']}",
        )

        return result

    except Exception as exc:
        result = {
            **state,
            "status": "failed",
            "error": f"Supervisor error: {exc}",
        }

        persist(
            result,
            "supervisor_failed",
            str(exc),
        )

        return result


def research_node(state: WorkflowState) -> WorkflowState:
    cancelled = cancellation_guard(state)
    if cancelled is not None:
        return cancelled
    try:
        result = research_agent.execute(state)

        persist(
            result,
            "research_agent_completed",
            "Research agent execution completed.",
        )

        if result.get("agent_result"):
            database.save_agent_result(
                workflow_id=result["workflow_id"],
                agent_name="research",
                result=result["agent_result"],
                success=True,
            )

        return result

    except Exception as exc:
        result = {
            **state,
            "status": "failed",
            "error": f"Research agent error: {exc}",
        }

        persist(
            result,
            "research_agent_failed",
            str(exc),
        )

        return result


def coding_node(state: WorkflowState) -> WorkflowState:
    cancelled = cancellation_guard(state)
    if cancelled is not None:
        return cancelled
    try:
        result = coding_agent.execute(state)

        persist(
            result,
            "coding_agent_completed",
            "Coding agent execution completed.",
        )

        if result.get("agent_result"):
            database.save_agent_result(
                workflow_id=result["workflow_id"],
                agent_name="coding",
                result=result["agent_result"],
                success=True,
            )

        return result

    except Exception as exc:
        result = {
            **state,
            "status": "failed",
            "error": f"Coding agent error: {exc}",
        }

        persist(
            result,
            "coding_agent_failed",
            str(exc),
        )

        return result


def analysis_node(state: WorkflowState) -> WorkflowState:
    cancelled = cancellation_guard(state)
    if cancelled is not None:
        return cancelled
    try:
        result = analysis_agent.execute(state)

        persist(
            result,
            "analysis_agent_completed",
            "Analysis agent execution completed.",
        )

        if result.get("agent_result"):
            database.save_agent_result(
                workflow_id=result["workflow_id"],
                agent_name="analysis",
                result=result["agent_result"],
                success=True,
            )

        return result

    except Exception as exc:
        result = {
            **state,
            "status": "failed",
            "error": f"Analysis agent error: {exc}",
        }

        persist(
            result,
            "analysis_agent_failed",
            str(exc),
        )

        return result


def tool_executor_node(state: WorkflowState) -> WorkflowState:
    cancelled = cancellation_guard(state)
    if cancelled is not None:
        return cancelled
    requests = state.get("tool_requests", [])

    if not requests:
        return state

    try:
        results = tool_executor.execute_all(requests)

        previous_results = state.get("tool_results", [])
        all_results = previous_results + results

        request_by_id = {
            request["id"]: request
            for request in requests
        }

        for tool_result in results:
            request = request_by_id.get(tool_result["id"], {})

            database.save_tool_call(
                workflow_id=state["workflow_id"],
                tool_name=tool_result["name"],
                arguments=request.get("args", {}),
                result=tool_result.get("result"),
                success=tool_result["success"],
                error=tool_result.get("error"),
            )

        failed = [
            result
            for result in results
            if not result["success"]
        ]

        if failed:
            errors = "; ".join(
                f'{item["name"]}: {item["error"]}'
                for item in failed
            )

            result = {
                **state,
                "tool_requests": [],
                "tool_results": all_results,
                "status": "failed",
                "error": f"Tool execution failed: {errors}",
            }

            persist(
                result,
                "tools_failed",
                errors,
            )

            return result

        result = {
            **state,
            "tool_requests": [],
            "tool_results": all_results,
            "error": "",
            "status": "running",
        }

        persist(
            result,
            "tools_executed",
            f"Executed {len(results)} tool call(s).",
        )

        return result

    except Exception as exc:
        result = {
            **state,
            "status": "failed",
            "error": f"Tool executor error: {exc}",
        }

        persist(
            result,
            "tool_executor_failed",
            str(exc),
        )

        return result


def aggregator_node(state: WorkflowState) -> WorkflowState:
    cancelled = cancellation_guard(state)
    if cancelled is not None:
        return cancelled
    try:
        agent_result = state.get("agent_result", "").strip()

        if not agent_result:
            result = {
                **state,
                "status": "failed",
                "error": "No agent result available for aggregation.",
            }

            persist(
                result,
                "workflow_failed",
                result["error"],
            )

            return result

        result = {
            **state,
            "final_result": agent_result,
            "status": "completed",
            "error": "",
        }

        persist(
            result,
            "workflow_completed",
            "Final result generated.",
        )

        return result

    except Exception as exc:
        result = {
            **state,
            "status": "failed",
            "error": f"Aggregator error: {exc}",
        }

        persist(
            result,
            "workflow_failed",
            str(exc),
        )

        return result


def reflection_node(state: WorkflowState) -> WorkflowState:
    cancelled = cancellation_guard(state)
    if cancelled is not None:
        return cancelled
    try:
        evaluation = reflection_agent.evaluate(state)

        decision = evaluation["decision"]
        reason = evaluation["reason"]

        previous_result = state.get("agent_result", "")
        attempt_number = state.get("retry_count", 0) + 1

        history = list(state.get("attempt_history", []))
        history.append(
            {
                "attempt": attempt_number,
                "agent": state.get("selected_agent", "research"),
                "result": previous_result,
                "reflection_decision": decision,
                "reflection_reason": reason,
            }
        )

        database.save_reflection_evaluation(
            workflow_id=state["workflow_id"],
            attempt=attempt_number,
            agent_name=state.get("selected_agent", "research"),
            result=previous_result,
            decision=decision,
            reason=reason,
        )

        if decision == "pass":
            result = {
                **state,
                "reflection_decision": "pass",
                "reflection_reason": reason,
                "attempt_history": history,
                "status": "running",
                "error": "",
            }

            persist(
                result,
                "reflection_passed",
                reason,
            )

            return result

        max_retries = state.get("max_retries", 2)
        retry_count = state.get("retry_count", 0)

        if retry_count >= max_retries:
            result = {
                **state,
                "reflection_decision": "retry",
                "reflection_reason": reason,
                "attempt_history": history,
                "status": "failed",
                "error": f"Maximum retries exhausted. {reason}",
            }

            persist(
                result,
                "reflection_failed",
                result["error"],
            )

            return result

        result = {
            **state,
            "retry_count": retry_count + 1,
            "reflection_decision": "retry",
            "reflection_reason": reason,
            "attempt_history": history,
            "agent_result": "",
            "final_result": "",
            "tool_requests": [],
            "tool_results": [],
            "tool_calls": [],
            "tool_round": 0,
            "status": "running",
            "error": "",
        }

        persist(
            result,
            "reflection_retry",
            f"Retry {retry_count + 1}/{max_retries}: {reason}",
        )

        return result

    except Exception as exc:
        result = {
            **state,
            "status": "failed",
            "error": f"Reflection agent error: {exc}",
        }

        persist(
            result,
            "reflection_failed",
            str(exc),
        )

        return result


def build_workflow():
    workflow = StateGraph(WorkflowState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("research", research_node)
    workflow.add_node("coding", coding_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("reflection", reflection_node)
    workflow.add_node("tool_executor", tool_executor_node)
    workflow.add_node("aggregator", aggregator_node)

    workflow.add_edge(START, "supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "research": "research",
            "coding": "coding",
            "analysis": "analysis",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "research",
        route_after_agent,
        {
            "tools": "tool_executor",
            "reflection": "reflection",
            "aggregator": "aggregator",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "coding",
        route_after_agent,
        {
            "tools": "tool_executor",
            "reflection": "reflection",
            "aggregator": "aggregator",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "analysis",
        route_after_agent,
        {
            "tools": "tool_executor",
            "reflection": "reflection",
            "aggregator": "aggregator",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "tool_executor",
        route_after_tools,
        {
            "research": "research",
            "coding": "coding",
            "analysis": "analysis",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "reflection",
        route_after_reflection,
        {
            "research": "research",
            "coding": "coding",
            "analysis": "analysis",
            "aggregator": "aggregator",
            "end": END,
        },
    )

    workflow.add_edge("aggregator", END)

    return workflow.compile()

