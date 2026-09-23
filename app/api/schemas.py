from pydantic import BaseModel, Field


class WorkflowCreateRequest(BaseModel):
    task: str = Field(min_length=1)
    max_retries: int = Field(default=2, ge=0, le=5)


class WorkflowCreateResponse(BaseModel):
    workflow_id: str
    status: str


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    task: str
    status: str
    selected_agent: str | None = None
    retry_count: int = 0
    final_result: str | None = None
    error: str | None = None


class WorkflowEventResponse(BaseModel):
    type: str
    message: str


class WorkflowEventsResponse(BaseModel):
    workflow_id: str
    events: list[WorkflowEventResponse]


class WorkflowCancelResponse(BaseModel):
    workflow_id: str
    status: str
    message: str
