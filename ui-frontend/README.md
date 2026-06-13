# Agent Operations — Human Approval UI

Chat-driven approval interface for reviewing and managing commitment lifecycles.

## Architecture

- **Backend**: FastAPI + OpenRouter (Python, in `langgraph-agents/ui/server.py`)
- **Frontend**: React + Vite (TypeScript, in `ui-frontend/`)

The frontend communicates with the backend via REST API. The backend proxies
LLM calls to OpenRouter and queries ArcadeDB directly.

## Quick Start

### 1. Backend

```bash
cd langgraph-agents
uv sync --group ui
uv run uvicorn ui.server:app --port 3001 --reload
```

Requires `ARCADEDB_URL`, `ARCADEDB_USER`, `ARCADEDB_PASSWORD`, and `OPENROUTER_API_KEY` environment variables.

### 2. Frontend

```bash
cd ui-frontend
npm install
npm run dev
```

Opens on `http://localhost:3002`. Requests to `/api/*` are proxied to the backend at port 3001.

### 3. Auth

Basic auth credentials default to `admin` / `agentops`. Override via `UI_USERNAME` and `UI_PASSWORD` environment variables on the backend.

## Features

- **Pending approvals** — view commitments waiting for human review
- **Approve / Reject / Defer** — one-click lifecycle actions
- **LLM chat** — ask questions about system state; the LLM queries ArcadeDB
- **Event log viewer** — toggle recent AgentSignal and AgentFinding events

## Deploy

The backend is part of the `langgraph-agents` Docker image. Start the UI as a Render web service:

```
uvicorn ui.server:app --host 0.0.0.0 --port $PORT
```

Set `UI_USERNAME` and `UI_PASSWORD` in Render's environment variables for production.
