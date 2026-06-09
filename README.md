# Agent Operations

An agent platform implementing the ExO 3.0 Intelligence Stack.

## Architecture

The platform consists of four agent types — exploratory, verification, objective, and orchestration — coordinated via an event log stored in ArcadeDB. Knowledge is maintained in a graph database with confidence decay. All agent output passes through a guardrail ensemble before delivery.

See [docs/plan.md](docs/plan.md) for the full build plan and [docs/requirements.md](docs/requirements.md) for requirements.

## Required Environment Variables

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | API key for OpenRouter (LLM routing) |
| `ARCADEDB_URL` | ArcadeDB HTTP endpoint |
| `ARCADEDB_USER` | ArcadeDB username |
| `ARCADEDB_PASSWORD` | ArcadeDB password |
| `POSTGRES_URL` | PostgreSQL connection string (LangGraph checkpoints) |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key for tracing |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key for tracing |
| `LANGFUSE_HOST` | Langfuse host URL |
| `AGENT_OPERATIONS_CONFIG_PATH` | Path to project configuration directory |
| `RENDER_API_KEY` | Render API key (for orchestration use) |

See `.env.example` for placeholder values.

## Local Development

```bash
uv sync
uv run ruff check .
uv run mypy .
uv run pytest tests/unit/
```

## Running Tests

```bash
uv run pytest tests/unit/ --cov=shared --cov=agents --cov-report=term-missing
uv run pytest tests/integration/
uv run pytest tests/agent/ -m 'not agent_regression'
```
