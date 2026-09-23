from fastapi import APIRouter, HTTPException, status

from app.api.schemas import (
    WorkflowCreateRequest,
    WorkflowCancelResponse,
    WorkflowCreateResponse,
    WorkflowEventResponse,
    WorkflowEventsResponse,
    WorkflowStatusResponse,
)
from app.database.repository import WorkflowRepository
from app.memory.manager import MemoryManager
from app.jobs.manager import JobManager


router = APIRouter(
    prefix="/workflows",
    tags=["workflows"],
)

job_manager = JobManager()
database = WorkflowRepository()
memory = MemoryManager()


@router.post(
    "",
    response_model=WorkflowCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_workflow(
    request: WorkflowCreateRequest,
) -> WorkflowCreateResponse:
    task = request.task.strip()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task cannot be empty.",
        )

    workflow_id = job_manager.submit(
        task=task,
        max_retries=request.max_retries,
    )

    return WorkflowCreateResponse(
        workflow_id=workflow_id,
        status="pending",
    )


@router.post(
    "/{workflow_id}/cancel",
    response_model=WorkflowCancelResponse,
)
def cancel_workflow(
    workflow_id: str,
) -> WorkflowCancelResponse:
    workflow = database.get_workflow(workflow_id)

    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found.",
        )

    try:
        workflow_status, message = job_manager.cancel(workflow_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return WorkflowCancelResponse(
        workflow_id=workflow_id,
        status=workflow_status,
        message=message,
    )



@router.get(
    "/{workflow_id}/events",
    response_model=WorkflowEventsResponse,
)
def get_workflow_events(
    workflow_id: str,
) -> WorkflowEventsResponse:
    workflow = database.get_workflow(workflow_id)

    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found.",
        )

    events = memory.get_events(workflow_id)

    return WorkflowEventsResponse(
        workflow_id=workflow_id,
        events=[
            WorkflowEventResponse(
                type=event["type"],
                message=event["message"],
            )
            for event in events
        ],
    )



@router.get(
    "/{workflow_id}",
    response_model=WorkflowStatusResponse,
)
def get_workflow_status(
    workflow_id: str,
) -> WorkflowStatusResponse:
    workflow = database.get_workflow(workflow_id)

    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found.",
        )

    return WorkflowStatusResponse(
        workflow_id=workflow.workflow_id,
        task=workflow.task,
        status=workflow.status,
        selected_agent=workflow.selected_agent,
        retry_count=(
            (workflow.state or {}).get("retry_count", 0)
        ),
        final_result=workflow.final_result,
        error=workflow.error,
    )
