from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import engine
from app.database.models import (
    AgentResult,
    ReflectionEvaluation,
    ToolCall,
    WorkflowExecution,
)


class WorkflowRepository:
    def create_workflow(
        self,
        workflow_id: str,
        task: str,
        status: str = "pending",
    ) -> WorkflowExecution:
        with Session(engine) as session:
            workflow = WorkflowExecution(
                workflow_id=workflow_id,
                task=task,
                status=status,
            )
            session.add(workflow)
            session.commit()
            session.refresh(workflow)
            return workflow

    def update_workflow(
        self,
        workflow_id: str,
        *,
        status: str | None = None,
        selected_agent: str | None = None,
        final_result: str | None = None,
        error: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> WorkflowExecution | None:
        with Session(engine) as session:
            stmt = select(WorkflowExecution).where(
                WorkflowExecution.workflow_id == workflow_id
            )
            workflow = session.scalar(stmt)

            if workflow is None:
                return None

            if status is not None:
                workflow.status = status

            if selected_agent is not None:
                workflow.selected_agent = selected_agent

            if final_result is not None:
                workflow.final_result = final_result

            if error is not None:
                workflow.error = error

            if state is not None:
                workflow.state = state

            session.commit()
            session.refresh(workflow)
            return workflow

    def get_workflow(self, workflow_id: str) -> WorkflowExecution | None:
        with Session(engine) as session:
            stmt = select(WorkflowExecution).where(
                WorkflowExecution.workflow_id == workflow_id
            )
            return session.scalar(stmt)

    def save_agent_result(
        self,
        workflow_id: str,
        agent_name: str,
        result: str,
        success: bool = True,
    ) -> AgentResult:
        with Session(engine) as session:
            agent_result = AgentResult(
                workflow_id=workflow_id,
                agent_name=agent_name,
                result=result,
                success=success,
            )
            session.add(agent_result)
            session.commit()
            session.refresh(agent_result)
            return agent_result

    def get_agent_results(self, workflow_id: str) -> list[AgentResult]:
        with Session(engine) as session:
            stmt = (
                select(AgentResult)
                .where(AgentResult.workflow_id == workflow_id)
                .order_by(AgentResult.id)
            )
            return list(session.scalars(stmt).all())

    def save_tool_call(
        self,
        workflow_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None,
        result: str | None,
        success: bool,
        error: str | None = None,
    ) -> ToolCall:
        with Session(engine) as session:
            tool_call = ToolCall(
                workflow_id=workflow_id,
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                success=success,
                error=error,
            )
            session.add(tool_call)
            session.commit()
            session.refresh(tool_call)
            return tool_call

    def get_tool_calls(self, workflow_id: str) -> list[ToolCall]:
        with Session(engine) as session:
            stmt = (
                select(ToolCall)
                .where(ToolCall.workflow_id == workflow_id)
                .order_by(ToolCall.id)
            )
            return list(session.scalars(stmt).all())

    def save_reflection_evaluation(
        self,
        workflow_id: str,
        attempt: int,
        agent_name: str,
        result: str,
        decision: str,
        reason: str,
    ) -> ReflectionEvaluation:
        with Session(engine) as session:
            evaluation = ReflectionEvaluation(
                workflow_id=workflow_id,
                attempt=attempt,
                agent_name=agent_name,
                result=result,
                decision=decision,
                reason=reason,
            )
            session.add(evaluation)
            session.commit()
            session.refresh(evaluation)
            return evaluation

    def get_reflection_evaluations(
        self,
        workflow_id: str,
    ) -> list[ReflectionEvaluation]:
        with Session(engine) as session:
            stmt = (
                select(ReflectionEvaluation)
                .where(
                    ReflectionEvaluation.workflow_id == workflow_id
                )
                .order_by(ReflectionEvaluation.attempt)
            )
            return list(session.scalars(stmt).all())

