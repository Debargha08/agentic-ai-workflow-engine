from app.llm.client import get_llm
from app.llm.prompts import EXECUTOR_PROMPT
from app.workflow.state import WorkflowState


class Executor:
    def __init__(self):
        self.llm = get_llm()

    def execute(self, state: WorkflowState) -> WorkflowState:
        task = state["task"]
        plan = state["plan"]

        steps = "\n".join(
            f"{index}. {step}"
            for index, step in enumerate(plan["steps"], start=1)
        )

        prompt = f"""
{EXECUTOR_PROMPT}

Original task:
{task}

Objective:
{plan["objective"]}

Execution steps:
{steps}
"""

        response = self.llm.invoke(prompt)

        return {
            **state,
            "result": response.content,
            "error": "",
        }
