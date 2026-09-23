from uuid import uuid4

from app.database.repository import WorkflowRepository
from app.database.connection import initialize_database
from app.memory.manager import MemoryManager
from app.workflow.graph import build_workflow


def main():
    initialize_database()
    workflow = build_workflow()
    memory = MemoryManager()
    database = WorkflowRepository()

    task = input("Enter your task: ").strip()

    if not task:
        print("No task provided.")
        return

    workflow_id = str(uuid4())

    initial_state = {
        "workflow_id": workflow_id,
        "task": task,
        "status": "pending",
        "retry_count": 0,
        "max_retries": 2,
        "attempt_history": [],
    }

    database.create_workflow(
        workflow_id=workflow_id,
        task=task,
        status="pending",
    )

    memory.record_event(
        workflow_id,
        {
            "type": "workflow_started",
            "message": "Workflow execution started.",
        },
    )

    result = workflow.invoke(initial_state)

    print("\n" + "=" * 60)
    print("MULTI-AGENT WORKFLOW RESULT")
    print("=" * 60)

    print("\nWorkflow ID:")
    print(workflow_id)

    print("\nStatus:")
    print(repr(result.get("status", "unknown")))

    if result.get("selected_agent"):
        print("\nSelected Agent:")
        print(result["selected_agent"])

    if result.get("tool_results"):
        print("\nTools Used:")
        for tool_result in result["tool_results"]:
            status = "SUCCESS" if tool_result["success"] else "FAILED"
            print(f"- {tool_result['name']}: {status}")

    if result.get("error"):
        print("\nERROR:")
        print(repr(result["error"]))
        return

    plan = result.get("plan")

    if plan:
        print("\nObjective:")
        print(plan["objective"])

        print("\nPlan:")
        for index, step in enumerate(plan["steps"], start=1):
            print(f"{index}. {step}")

    final_result = result.get("final_result")

    if not final_result:
        print("\nERROR:")
        print("Workflow ended without a final result.")
        return

    print("\nFinal Result:")
    print(final_result)

    events = memory.get_events(workflow_id)

    print("\nEvents Recorded:")
    for event in events:
        print(
            f"- {event['type']}: "
            f"{event['message']}"
        )


if __name__ == "__main__":
    main()
