# Agentic AI Workflow Engine

An autonomous multi-agent workflow platform for planning, executing, monitoring, and validating complex AI tasks.

The system combines multi-agent orchestration, tool calling, persistent memory, asynchronous execution, reflection, retry logic, and production-oriented APIs into a single workflow engine.

## Architecture

```text
                         CLIENT
                           |
                           v
                    +-------------+
                    |   FastAPI   |
                    |     API     |
                    +------+------+
                           |
                           v
                    +-------------+
                    | Job Manager |
                    +------+------+
                           |
                           v
                 +--------------------+
                 |  Workflow Engine   |
                 |     LangGraph      |
                 +---------+----------+
                           |
              +------------+------------+
              |            |            |
              v            v            v
        Research Agent  Coding Agent  Analysis Agent
              |            |            |
              +------------+------------+
                           |
                           v
                    Tool Executor
                           |
                           v
                    Reflection / Retry
                           |
              +------------+------------+
              |                         |
              v                         v
           Redis                   PostgreSQL
```
## Core Capabilities

- Multi-agent workflow orchestration
- Supervisor-based agent routing
- Structured workflow planning
- Tool calling and execution
- Repository and file inspection
- Controlled Python execution
- Allowlisted shell execution
- Short-term workflow memory
- Persistent PostgreSQL storage
- Redis-based state and event persistence
- Reflection and retry mechanisms
- Maximum retry enforcement
- Asynchronous workflow execution
- Workflow cancellation
- Real-time workflow events
- Execution metrics
- Health monitoring
- Dockerized deployment
- Automated CI testing

## Multi-Agent Architecture

The workflow engine uses specialized agents coordinated through a supervisor.

### Supervisor

Determines which specialized agent should handle a task.

### Research Agent

Handles information-oriented tasks and repository inspection workflows.

### Coding Agent

Handles programming, repository, and implementation-oriented tasks.

### Analysis Agent

Handles reasoning, comparison, explanation, and analytical tasks.

### Reflection Agent

Evaluates workflow results and determines whether the result should be accepted or retried.

## Workflow

A typical workflow follows:

Task Submission
      |
      v
   Supervisor
      |
      v
 Agent Selection
      |
      v
 Agent Execution
      |
      v
  Tool Calling
      |
      v
 Result Generation
      |
      v
   Reflection
      |
   +--+--+
   |     |
  Pass  Retry
   |     |
   v     v
Accept  Re-execute

Retry attempts are bounded to prevent uncontrolled execution.

## Tool Calling

The engine provides controlled tools for agent workflows:

| Tool | Purpose |
|------|---------|
| `read_file` | Read files within the allowed workspace |
| `code_search` | Search files and directories |
| `python_execute` | Execute Python code with a timeout |
| `shell_execute` | Execute allowlisted shell commands |

Tool execution is routed through a centralized tool registry and executor.

## Security Controls

The tool layer includes several safety mechanisms:

- Workspace boundary validation
- Path traversal protection
- Restricted shell command allowlist
- Subprocess timeouts
- Explicit tool schemas
- Controlled tool routing
- Retry limits

## Memory & Persistence

The system uses Redis and PostgreSQL for workflow state and persistence.

### Redis

Used for:

- Short-term workflow memory
- Workflow events
- State persistence
- Cancellation signals

### PostgreSQL

Used for:

- Workflow executions
- Agent results
- Tool calls
- Reflection evaluations
- Persistent workflow state

## Asynchronous Execution & Monitoring

Workflows are submitted through FastAPI and executed asynchronously using a background worker pool.

The system supports:

- Background workflow execution
- Workflow status tracking
- Workflow cancellation
- Event retrieval
- Execution metrics
- Graceful worker shutdown

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Execution metrics |
| `POST` | `/workflows` | Submit a workflow |
| `GET` | `/workflows/{workflow_id}` | Get workflow status |
| `GET` | `/workflows/{workflow_id}/events` | Get workflow events |
| `POST` | `/workflows/{workflow_id}/cancel` | Cancel a workflow |

Interactive API documentation is available through FastAPI.

## Local LLM

The project uses a locally hosted Ollama model for agent reasoning.

- **Model:** Qwen 2.5 3B
- **Runtime:** Ollama

No external LLM API is required for the default setup.

## Tech Stack

- **Language:** Python
- **Agent Orchestration:** LangGraph
- **LLM Framework:** LangChain
- **LLM Runtime:** Ollama
- **Model:** Qwen 2.5 3B
- **API:** FastAPI
- **Database:** PostgreSQL
- **State / Cache:** Redis
- **Containerization:** Docker
- **Testing:** Pytest
- **CI:** GitHub Actions

## Project Structure

```text
agentic-ai-workflow-engine/
├── .github/
│   └── workflows/
│       └── ci.yml
├── app/
│   ├── agents/
│   ├── api/
│   ├── database/
│   ├── evaluation/
│   ├── jobs/
│   ├── llm/
│   ├── memory/
│   ├── monitoring/
│   ├── tools/
│   └── workflow/
├── tests/
│   ├── evaluation/
│   ├── integration/
│   └── unit/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
└── README.md

```
## Running Locally

Clone the repository and install the dependencies:

```bash
git clone https://github.com/Debargha08/agentic-ai-workflow-engine.git
cd agentic-ai-workflow-engine
pip install -r requirements.txt
```

Start the infrastructure:

```bash
docker compose up -d postgres redis
```

Start Ollama:

```bash
ollama serve
```

Run the API:

```bash
uvicorn app.api.server:app --reload
```

The API will be available at:

http://localhost:8000

## Docker Deployment

Build and start the complete application stack with Docker Compose:

```bash
docker compose up -d --build
```

Check the running services:

```bash
docker compose ps
```

Verify the API health endpoint:

```bash
curl http://localhost:8000/health
```

The stack includes:

- FastAPI application
- PostgreSQL
- Redis
- Docker health checks

The application container connects to the host Ollama runtime through `host.docker.internal`.

## Testing

Run the complete test suite:

```bash
python3 -m pytest -q
```

Compile the application and tests:

```bash
python3 -m compileall -q app tests
```

The test suite covers:

- Unit tests
- API integration tests
- Evaluation and retry behavior
- Container integration
- Graceful shutdown and resource cleanup

## Continuous Integration

GitHub Actions automatically:

1. Sets up Python 3.10
2. Installs project dependencies
3. Compiles the application and tests
4. Runs the full test suite

## Production Verification

The system was verified through local and containerized testing.

Verification included:

- Full automated test suite
- Python compilation checks
- Docker image build
- PostgreSQL health verification
- Redis health verification
- FastAPI health endpoint
- Containerized workflow execution
- End-to-end API workflow submission
- Workflow status tracking
- Graceful worker shutdown

The final verification confirmed that the complete workflow engine runs successfully in the Dockerized environment.
## Design Principles

- Modular agent architecture
- Explicit workflow state
- Controlled tool execution
- Persistent workflow state
- Bounded retries
- Failure-aware execution
- Observable workflows
- Safe resource cleanup
- Local-first AI infrastructure

## Project Goal

The goal of this project is to provide a production-oriented foundation for autonomous AI systems that can:

- Plan complex tasks
- Use tools safely
- Maintain persistent state
- Evaluate generated results
- Recover through controlled retries
- Execute workflows asynchronously

---

Built by **Debargha Dutta**
