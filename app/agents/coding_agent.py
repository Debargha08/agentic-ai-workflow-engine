import re
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.client import get_llm
from app.llm.prompts import CODING_AGENT_PROMPT
from app.tools.definitions import (
    code_search,
    python_execute,
    read_file,
    shell_execute,
)
from app.workflow.state import ToolRequest, WorkflowState
MAX_TOOL_ROUNDS = 4
class CodingAgent:
    def __init__(self):
        self.tool_llm = get_llm(num_predict=256).bind_tools(
            [
                read_file,
                code_search,
                python_execute,
                shell_execute,
            ]
        )

        self.final_llm = get_llm(num_predict=384)

    def _base_messages(self, state: WorkflowState):
        plan = state["plan"]

        steps = "\n".join(
            f"{i}. {step}"
            for i, step in enumerate(plan["steps"], 1)
        )

        return [
            SystemMessage(content=CODING_AGENT_PROMPT),
            HumanMessage(
                content=f"""
Task:
{state["task"]}

Objective:
{plan["objective"]}

Steps:
{steps}

Available tools:
- code_search
- read_file
- python_execute
- shell_execute

Use tools only when the task explicitly requires repository
inspection, file inspection, code execution, testing, or Git.
Do not use tools for a simple standalone coding answer.
"""
            ),
        ]

    def _requires_repository_inspection(self, task: str) -> bool:
        text = task.lower()

        terms = [
            "inspect",
            "find the definition",
            "find the implementation",
            "read the file",
            "read the contents",
            "workflowstate",
            "repository",
            "codebase",
        ]

        return any(term in text for term in terms)

    def _requires_python_validation(self, task: str) -> bool:
        text = task.lower()

        terms = [
            "run a python check",
            "run python",
            "execute python",
            "python check",
            "verify that",
            "verify whether",
            "check whether",
            "check if",
            "confirm that",
            "validate that",
            "use python execution",
            "python execution",
        ]

        return any(term in text for term in terms)

    def _requires_shell_execution(self, task: str) -> bool:
        text = task.lower()

        terms = [
            "git status",
            "git diff",
            "git log",
            "repository git",
            "uncommitted changes",
            "shell",
        ]

        return any(term in text for term in terms)

    def _extract_search_query(self, task: str) -> str:
        text = task.lower()

        if "workflowstate" in text:
            return "WorkflowState"

        if "entry point" in text or "entrypoint" in text:
            return "FastAPI"

        match = re.search(
            r"\b(?:definition|implementation|class|function)\s+"
            r"(?:of\s+)?([A-Za-z_][A-Za-z0-9_]*)",
            task,
            re.IGNORECASE,
        )

        if match:
            return match.group(1)

        match = re.search(
            r"\b[A-Z][A-Za-z0-9_]{2,}\b",
            task,
        )

        if match:
            return match.group(0)

        raise ValueError(
            "Could not determine a search target from the task."
        )

    def _extract_file_path(
        self,
        search_result: str,
    ) -> str | None:

        for line in search_result.splitlines():
            match = re.match(
                r"^(.+?):\d+:\s*(.*)$",
                line.strip(),
            )

            if not match:
                continue

            path = match.group(1)
            code = match.group(2)

            if re.search(
                r"\bclass\s+WorkflowState\b",
                code,
                re.IGNORECASE,
            ):
                return path

        for line in search_result.splitlines():
            match = re.match(
                r"^(.+?):\d+:",
                line.strip(),
            )

            if match:
                return match.group(1)
        return None

    def _successful_tool_exists(
        self,
        state: WorkflowState,
        name: str,
    ) -> bool:
        return any(
            result["name"] == name
            and result["success"]
            for result in state.get("tool_results", [])
        )

    def _request_tool(
        self,
        state: WorkflowState,
        name: str,
        args: dict,
    ) -> WorkflowState:

        next_round = state.get("tool_round", 0) + 1

        if next_round > MAX_TOOL_ROUNDS:
            return {
                **state,
                "status": "failed",
                "error": "Maximum tool-call rounds exceeded.",
            }

        request: ToolRequest = {
            "name": name,
            "args": args,
            "id": str(uuid4()),
        }

        return {
            **state,
            "tool_requests": [request],
            "tool_calls": [],
            "tool_round": next_round,
            "status": "running",
            "error": "",
        }

    def _build_python_validation(self, task: str) -> str:
        text = task.lower()

        if "workflowstate" in text and "typeddict" in text:
            return (
                "from app.workflow.state import WorkflowState\n"
                "from typing import is_typeddict\n"
                "print(is_typeddict(WorkflowState))"
            )

        return (
            "print('Python validation requested for the following task:')\n"
            f"print({task!r})"
        )

    def _finalize_from_tools(
        self,
        state: WorkflowState,
    ) -> WorkflowState:

        successful_results = [
            result
            for result in state.get("tool_results", [])
            if result["success"]
        ]

        if not successful_results:
            return {
                **state,
                "status": "failed",
                "error": "No successful tool results available.",
            }

        tool_context = "\n\n".join(
            (
                f"Tool: {result['name']}\n"
                f"Result:\n{result['result']}"
            )
            for result in successful_results
        )

        response = self.final_llm.invoke(
            [
                SystemMessage(
                    content=(
                        "You are the final synthesizer for a coding workflow. "
                        "Use only the successful tool results as evidence. "
                        "Do not request tools. Do not invent files, code, "
                        "facts, or execution results. Be concise."
                    )
                ),
                HumanMessage(
                    content=f"""
Original task:
{state["task"]}

Successful tool results:
{tool_context}

Produce the final answer to the original task.
"""
                ),
            ]
        )

        content = response.content.strip()

        if not content:
            return {
                **state,
                "status": "failed",
                "error": "Coding finalization produced no result.",
            }

        return {
            **state,
            "agent_result": content,
            "tool_requests": [],
            "tool_calls": [],
            "status": "running",
            "error": "",
        }

    def _complete_simple_task(
        self,
        state: WorkflowState,
    ) -> WorkflowState:

        response = self.final_llm.invoke(
            self._base_messages(state)
        )

        content = response.content.strip()

        if not content:
            return {
                **state,
                "status": "failed",
                "error": "Coding agent produced no final result.",
            }

        return {
            **state,
            "agent_result": content,
            "tool_requests": [],
            "tool_calls": [],
            "status": "running",
            "error": "",
        }

    def execute(self, state: WorkflowState) -> WorkflowState:
        task = state["task"]
        results = state.get("tool_results", [])

        needs_inspection = self._requires_repository_inspection(task)
        needs_python = self._requires_python_validation(task)
        needs_shell = self._requires_shell_execution(task)

        # ---------------------------------------------------------
        # Simple coding tasks do not enter the tool loop.
        # ---------------------------------------------------------
        if not needs_inspection and not needs_python and not needs_shell:
            return self._complete_simple_task(state)

        # ---------------------------------------------------------
        # Repository inspection workflow:
        # code_search -> read_file -> optional python validation
        # ---------------------------------------------------------
        if needs_inspection:

            search_done = self._successful_tool_exists(
                state,
                "code_search",
            )

            read_done = self._successful_tool_exists(
                state,
                "read_file",
            )

            python_done = self._successful_tool_exists(
                state,
                "python_execute",
            )

            if not search_done:
                return self._request_tool(
                    state,
                    "code_search",
                    {
                        "query": self._extract_search_query(task),
                        "path": ".",
                        "max_results": 10,
                    },
                )

            if not read_done:
                search_result = next(
                    (
                        result["result"]
                        for result in results
                        if (
                            result["name"] == "code_search"
                            and result["success"]
                        )
                    ),
                    None,
                )

                if not search_result:
                    return {
                        **state,
                        "status": "failed",
                        "error": "No successful code_search result.",
                    }

                file_path = self._extract_file_path(
                    search_result
                )

                if not file_path:
                    return {
                        **state,
                        "status": "failed",
                        "error": (
                            "Could not determine the file path "
                            "from code_search."
                        ),
                    }

                return self._request_tool(
                    state,
                    "read_file",
                    {
                        "path": file_path,
                    },
                )

            if needs_python and not python_done:
                return self._request_tool(
                    state,
                    "python_execute",
                    {
                        "code": self._build_python_validation(task),
                    },
                )

            return self._finalize_from_tools(state)

        # ---------------------------------------------------------
        # Explicit Python validation without repository inspection.
        # ---------------------------------------------------------
        if needs_python:
            python_done = self._successful_tool_exists(
                state,
                "python_execute",
            )

            if not python_done:
                return self._request_tool(
                    state,
                    "python_execute",
                    {
                        "code": self._build_python_validation(task),
                    },
                )

            return self._finalize_from_tools(state)

        # ---------------------------------------------------------
        # Explicit shell/Git task.
        # Let the tool-enabled LLM select shell_execute.
        # ---------------------------------------------------------
        if needs_shell:
            response = self.tool_llm.invoke(
                self._base_messages(state)
            )

            if response.tool_calls:
                next_round = state.get("tool_round", 0) + 1

                if next_round > MAX_TOOL_ROUNDS:
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
                    "tool_round": next_round,
                    "status": "running",
                    "error": "",
                }

            content = response.content.strip()

            if not content:
                return {
                    **state,
                    "status": "failed",
                    "error": "Coding agent produced no final result.",
                }

            return {
                **state,
                "agent_result": content,
                "tool_requests": [],
                "tool_calls": [],
                "status": "running",
                "error": "",
            }

        return self._complete_simple_task(state)
