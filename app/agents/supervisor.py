import json
import re

from app.llm.client import get_llm
from app.llm.prompts import SUPERVISOR_PROMPT
from app.workflow.state import Plan


VALID_AGENTS = {"research", "coding", "analysis"}


class Supervisor:
    def __init__(self):
        self.llm = get_llm()

    def _fast_route(self, task: str) -> str | None:
        text = task.lower().strip()

        # Tasks that explicitly require execution, testing, importing,
        # validation, or repository commands belong to Coding.
        execution_patterns = [
            r"\brun\s+(a\s+)?python\s+(check|script|test)\b",
            r"\bexecute\b",
            r"\btest\b",
            r"\bpytest\b",
            r"\bverify\b",
            r"\bvalidate\b",
            r"\bimport\b.*\bcheck\b",
            r"\bcheck\s+(whether|if|that)\b",
            r"\bconfirm\b.*\b(import|implementation|code)\b",
            r"\bgit\s+(status|diff|log)\b",
            r"\buncommitted\s+changes\b",
            r"\brepository\s+(status|changes|diff|history)\b",
            r"\binspect\s+(the\s+)?(python\s+)?(project|repository|codebase)\b",
        ]

        coding_patterns = [
            r"\bwrite\s+(a|an|the)?\s*(python|java|javascript|c\+\+)?\s*(function|class|script|program|code)\b",
            r"\bimplement\b",
            r"\bdebug\b",
            r"\bdebugging\b",
            r"\bfix\s+(the|this)?\s*code\b",
            r"\bcreate\s+(a|an)?\s*(function|class|script|program)\b",
            r"\bbuild\s+(a|an)?\s*(application|service|api|script)\b",
        ]

        analysis_patterns = [
            r"\banalyze\b",
            r"\banalysis\b",
            r"\bevaluate\b",
            r"\bevaluation\b",
            r"\badvantages\s+and\s+disadvantages\b",
            r"\bpros\s+and\s+cons\b",
            r"\btrade[- ]offs?\b",
        ]

        research_patterns = [
            r"\bexplain\b",
            r"\bexplanation\b",
            r"\bdifference(s)?\s+between\b",
            r"\bcompare\b",
            r"\bcomparison\b",
            r"\bsummarize\b",
            r"\bsummary\b",
            r"\bresearch\b",
            r"\boverview\b",
            r"\bwhat\s+is\b",
            r"\bwhat\s+are\b",
            r"\bdescribe\b",
        ]

        # Execution/testing intent has the highest priority.
        if any(re.search(pattern, text) for pattern in execution_patterns):
            return "coding"

        if any(re.search(pattern, text) for pattern in coding_patterns):
            return "coding"

        if any(re.search(pattern, text) for pattern in analysis_patterns):
            return "analysis"

        if any(re.search(pattern, text) for pattern in research_patterns):
            return "research"

        return None

    def _llm_route(self, task: str) -> Plan:
        prompt = f"""
{SUPERVISOR_PROMPT}

User task:
{task}
"""

        response = self.llm.invoke(prompt)
        content = response.content.strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")

            if start == -1 or end == -1:
                raise ValueError("Supervisor returned invalid JSON.")

            data = json.loads(content[start:end + 1])

        objective = data.get("objective")
        agent = data.get("agent")
        steps = data.get("steps")

        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("Plan objective is missing or invalid.")

        if agent not in VALID_AGENTS:
            raise ValueError(f"Invalid agent selection: {agent}")

        if not isinstance(steps, list) or not steps:
            raise ValueError("Plan steps are missing or invalid.")

        if not all(
            isinstance(step, str) and step.strip()
            for step in steps
        ):
            raise ValueError("Plan contains invalid steps.")

        return {
            "objective": objective.strip(),
            "agent": agent,
            "steps": [step.strip() for step in steps],
        }

    def create_plan(self, task: str) -> Plan:
        fast_agent = self._fast_route(task)

        if fast_agent:
            return {
                "objective": task.strip(),
                "agent": fast_agent,
                "steps": [
                    "Understand the task requirements",
                    "Execute the required work",
                    "Validate the result",
                ],
            }

        return self._llm_route(task)
