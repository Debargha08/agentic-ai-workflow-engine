import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.client import get_llm
from app.workflow.state import ReflectionDecision, WorkflowState


class ReflectionAgent:
    """
    Evaluates an agent result against the original task.

    The reflection agent is deliberately unbound:
    it must never call workflow tools.
    """

    def __init__(self):
        self.llm = get_llm(num_predict=256)

    def _parse_decision(self, content: str) -> tuple[ReflectionDecision, str]:
        decision_match = re.search(
            r"\bDECISION\s*:\s*(PASS|RETRY)\b",
            content,
            re.IGNORECASE,
        )

        if not decision_match:
            return (
                "retry",
                "Reflection output could not be parsed into PASS or RETRY.",
            )

        decision: ReflectionDecision = (
            "pass"
            if decision_match.group(1).upper() == "PASS"
            else "retry"
        )

        reason_match = re.search(
            r"\bREASON\s*:\s*(.+)",
            content,
            re.IGNORECASE | re.DOTALL,
        )

        reason = (
            reason_match.group(1).strip()
            if reason_match
            else "No reflection reason was provided."
        )

        return decision, reason

    def evaluate(self, state: WorkflowState) -> dict:
        result = state.get("agent_result", "").strip()

        if not result:
            return {
                "decision": "retry",
                "reason": "Agent produced no result.",
            }

        plan = state.get("plan", {})
        objective = plan.get("objective", state.get("task", ""))

        response = self.llm.invoke(
            [
                SystemMessage(
                    content=(
                        "You are a strict workflow reflection agent.\n"
                        "Evaluate whether the agent result satisfies the "
                        "user's task.\n\n"
                        "Check:\n"
                        "1. Relevance to the task.\n"
                        "2. Completeness for the requested objective.\n"
                        "3. Internal consistency.\n"
                        "4. Respect for explicit task constraints.\n"
                        "5. Whether the answer is usable without another "
                        "mandatory correction.\n"
                        "6. Reject responses that only restate the task, "
                        "describe a plan, describe tools, or explain what "
                        "the agent would do instead of actually answering.\n"
                        "7. Reject meta-responses such as 'the task requires...' "
                        "when they do not provide the requested answer.\n\n"
                        "Return exactly this format:\n"
                        "DECISION: PASS or RETRY\n"
                        "REASON: one concise explanation"
                    )
                ),
                HumanMessage(
                    content=f"""
Original task:
{state["task"]}

Objective:
{objective}

Agent result:
{result}
"""
                ),
            ]
        )

        decision, reason = self._parse_decision(response.content.strip())

        return {
            "decision": decision,
            "reason": reason,
        }
