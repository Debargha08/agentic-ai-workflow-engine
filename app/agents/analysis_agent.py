from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.llm.client import get_llm
from app.llm.prompts import ANALYSIS_AGENT_PROMPT
from app.tools.definitions import code_search, read_file
from app.workflow.state import ToolRequest, WorkflowState


MAX_TOOL_ROUNDS = 2


class AnalysisAgent:
    def __init__(self):
        self.llm = get_llm().bind_tools([read_file, code_search])

    def _base_messages(self, state: WorkflowState):
        plan = state["plan"]

        steps = "\n".join(
            f"{i}. {step}"
            for i, step in enumerate(plan["steps"], 1)
        )

        return [
            SystemMessage(content=ANALYSIS_AGENT_PROMPT),
            HumanMessage(
                content=f"""
Task:
{state["task"]}

Objective:
{plan["objective"]}

Steps:
{steps}

Use the available tools when necessary.
"""
            ),
        ]

    def execute(self, state: WorkflowState) -> WorkflowState:
        messages = self._base_messages(state)

        previous_tool_calls = state.get("tool_calls", [])
        tool_results = state.get("tool_results", [])

        if previous_tool_calls:
            messages.append(
                AIMessage(
                    content="",
                    tool_calls=previous_tool_calls,
                )
            )

            for result in tool_results:
                messages.append(
                    ToolMessage(
                        content=(
                            result["result"]
                            if result["success"]
                            else f'ERROR: {result["error"]}'
                        ),
                        tool_call_id=result["id"],
                        name=result["name"],
                    )
                )

        response = self.llm.invoke(messages)

        if response.tool_calls:
            current_round = state.get("tool_round", 0) + 1

            if current_round > MAX_TOOL_ROUNDS:
                return {
                    **state,
                    "status": "failed",
                    "error": "Maximum tool-call rounds exceeded.",
                }

            requests: list[ToolRequest] = [
                {
                    "name": call["name"],
                    "args": call["args"],
                    "id": call["id"],
                }
                for call in response.tool_calls
            ]

            return {
                **state,
                "tool_requests": requests,
                "tool_calls": response.tool_calls,
                "tool_round": current_round,
                "status": "running",
                "error": "",
            }

        return {
            **state,
            "agent_result": response.content.strip(),
            "tool_requests": [],
            "tool_calls": [],
            "status": "running",
            "error": "",
        }
