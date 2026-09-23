from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.workflows import job_manager, router as workflows_router
from app.database.connection import initialize_database
from app.monitoring.metrics import metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()

    try:
        yield
    finally:
        job_manager.shutdown()


app = FastAPI(
    title="Agentic AI Workflow Engine",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(workflows_router)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "agentic-workflow-engine",
    }


@app.get("/metrics")
def get_metrics():
    return metrics.snapshot()
