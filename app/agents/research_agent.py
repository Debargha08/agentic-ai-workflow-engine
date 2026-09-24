import re
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.client import get_llm
from app.llm.prompts import RESEARCH_AGENT_PROMPT
from app.tools.definitions import code_search, read_file
from app.workflow.state import ToolRequest, WorkflowState


MAX_TOOL_ROUNDS = 2


class ResearchAgent:
    def __init__(self):
        self.llm = get_llm().bind_tools(
            [read_file, code_search]
        )
        self.final_llm = get_llm(num_predict=384)

    def _base_messages(self, state: WorkflowState):
        plan = state["plan"]

        steps = "\n".join(
            f"{i}. {step}"
            for i, step in enumerate(plan["steps"], 1)
        )

        return [
            SystemMessage(content=RESEARCH_AGENT_PROMPT),
            HumanMessage(
                content=f"""
Task:
{state["task"]}

Objective:
{plan["objective"]}

Steps:
{steps}

Use actual tool results when they are available.
Do not invent project files, fields, or contents.
"""
            ),
        ]

    def _requires_file_inspection(self, task: str) -> bool:
        text = task.lower()

        terms = [
            "inspect",
            "read",
            "contents",
            "definition",
            "fields",
            "implementation",
            "file",
            "entry point",
        ]

        return any(term in text for term in terms)

    def _extract_search_query(self, task: str) -> str:
        if "entry point" in task.lower() or "entrypoint" in task.lower():
            return "FastAPI"

        if "workflowstate" in task.lower():
            return "WorkflowState"

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

    def _extract_path(self, search_result: str) -> str | None:
        definition_matches = []

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
                definition_matches.append(path)

        if definition_matches:
            return definition_matches[0]

        for line in search_result.splitlines():
            match = re.match(
                r"^(.+?):\d+:",
                line.strip(),
            )

            if match:
                return match.group(1)

        return None

    def _request(
        self,
        name: str,
        args: dict,
        state: WorkflowState,
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
            "tool_calls": [request],
            "tool_round": next_round,
            "status": "running",
            "error": "",
        }

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
                        "Answer the user's task using the tool results "
                        "as the source of truth. Do not invent missing "
                        "file contents or fields. Be concise."
                    )
                ),
                HumanMessage(
                    content=f"""
Original task:
{state["task"]}

Tool results:
{tool_context}

Now answer the original task directly.
"""
                ),
            ]
        )

        content = response.content.strip()

        if not content:
            return {
                **state,
                "status": "failed",
                "error": "Research finalization produced no result.",
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

        if self._requires_file_inspection(task):

            has_search = any(
                result["name"] == "code_search"
                for result in results
            )

            has_read = any(
                result["name"] == "read_file"
                and result["success"]
                for result in results
            )

            if not has_search:
                query = self._extract_search_query(task)

                return self._request(
                    "code_search",
                    {
                        "query": query,
                        "path": ".",
                        "max_results": 10,
                    },
                    state,
                )

            if not has_read:
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
                        "error": "code_search returned no usable result.",
                    }

                path = self._extract_path(search_result)

                if not path:
                    return {
                        **state,
                        "status": "failed",
                        "error": (
                            "Could not determine the file path "
                            "from code_search results."
                        ),
                    }

                return self._request(
                    "read_file",
                    {
                        "path": path,
                    },
                    state,
                )

            # Both tools have completed.
            return self._finalize_from_tools(state)

        # Normal research task without forced repository inspection.
        # Answer the user's task directly. Do not generate a plan or tool workflow.
        response = self.final_llm.invoke(
            [
                SystemMessage(
                    content=(
                        "You are a research assistant. "
                        "Answer the user's task directly and clearly. "
                        "Do not describe the workflow, planning steps, or tools. "
                        "Do not say what you would do. "
                        "Provide the actual answer requested by the user."
                    )
                ),
                HumanMessage(
                    content=f"""
User task:
{state["task"]}

Write the answer directly.
"""
                ),
            ]
        )

        content = response.content.strip()

        if not content:
            return {
                **state,
                "status": "failed",
                "error": "Research agent produced no final result.",
            }

        return {
            **state,
            "agent_result": content,
            "tool_requests": [],
            "tool_calls": [],
            "status": "running",
            "error": "",
        }
