---
name: verify
description: Post-execution empirical verification. Build the project, run the full test suite, start the server and call the API, run pre-written E2E tests, and use BrowserToolSet to navigate the UI as a real user. Apply after all files have been written, before the review skill.
---

# Verify

Apply this skill after all code changes are complete, before the `review` skill. This is empirical verification — actually run the thing and observe that it works. Thoroughness matters more than speed.

## Principles

- **Prefer repo-defined commands** over guessing. Check CI workflows, Makefile/Taskfile/Justfile, and `package.json` scripts first.
- **Run the full suite**. Do not short-circuit to a subset to save time.
- **Report status per step**, not just overall pass/fail.
- **Always clean up**: stop any background process you started before moving on.

---

## Step 1: Discover commands

Check these sources **in order** to find build, test, start, and E2E commands:

### 1a. CI workflow
Look for `.github/workflows/*.yml` (or `.circleci/`, `.buildkite/`). Find the build/test/e2e job steps and extract the exact commands used.

### 1b. Makefile / Taskfile / Justfile
Look for targets named `build`, `test`, `start`, `serve`, `smoke`, `e2e`, `check`.

### 1c. `package.json` scripts
Read all `scripts` entries. Common names: `build`, `test`, `start`, `dev`, `serve`, `e2e`, `test:e2e`, `smoke`.

### 1d. Language heuristics (fallback only)

| Marker file | Build | Test | Start |
|-------------|-------|------|-------|
| `pyproject.toml` / `setup.py` | `pip install -e .` | `pytest` or `python -m unittest` | Inspect `__main__` / `uvicorn` / `gunicorn` entry |
| `package.json` | `npm run build` | `npm test` | `npm start` or `npm run dev` |
| `*.csproj` / `*.sln` | `dotnet build` | `dotnet test` | `dotnet run --project <project>` |
| `go.mod` | `go build ./...` | `go test ./...` | Detect `main` package |
| `Cargo.toml` | `cargo build` | `cargo test` | `cargo run` |

---

## Step 2: Build

Run the build command. Fix any build failures before proceeding — a failing build means nothing else is meaningful.

---

## Step 3: Full test suite

Run the complete test suite. Do not restrict to affected files or modules — regressions can appear anywhere.

Do not run in watch mode.

---

## Step 4: Start the server and test the API / UI

If the project exposes an HTTP server (API, web app, or full-stack application):

### 4a. Start the server

1. Identify the start command from Step 1 (e.g., `npm start`, `uvicorn app:app --port 8000`, `dotnet run`)
2. Launch it as a background process
3. Wait for readiness: poll `http://localhost:<port>/health` (or `/`, or the known health route), checking every 2 seconds until it responds
4. If the server fails to start or never becomes ready, mark this step `failed`, capture the startup log, terminate the process, and continue to Step 5

### 4b. Call the API

Once ready, exercise the application with HTTP calls. Prefer repo-defined smoke routes. Otherwise use these heuristics in order:

1. **Health / readiness endpoint**: `GET /health`, `GET /ready`, `GET /healthz` — expect 2xx
2. **Key application routes**: identify the important routes from route definitions, controllers, or OpenAPI spec. Send `GET` requests (safe reads only). Verify 2xx or expected 3xx.
3. **Happy-path POST** (if changed code is a mutation): send a minimal valid payload and verify the response structure matches the expected schema

For each call, record: method, URL, status code, response body excerpt (first 200 chars), pass/fail.

### 4c. Stop the server

Terminate the background process. Confirm it has exited before continuing.

---

## Step 5: Browser UI verification

### 5a. Run pre-written E2E test suite (if present)

If any of the following exist, run the suite:
- `playwright.config.ts` / `playwright.config.js` → `npx playwright test --reporter=list`
- `cypress.config.ts` / `cypress.config.js` → `npx cypress run`
- `scripts.e2e` or `scripts.test:e2e` in `package.json` → run that script

On failure, include the last 50 lines of output and any screenshot paths.

### 5b. Agent-driven browser verification

If the application is web-facing (serves HTML at localhost after Step 4), use `BrowserToolSet` to verify the UI as a real user would — regardless of whether a pre-written E2E suite also ran.

**How to use it**: `BrowserToolSet` is already available as a tool. Navigate and interact using natural language intent:
1. Navigate to `http://localhost:<port>`
2. Verify the page loads and renders key content (no blank page, no error screen, no 500)
3. Exercise the specific UI area affected by the current change:
   - If a form was changed: fill it in and submit; verify the expected outcome
   - If a list/table was changed: verify data displays correctly
   - If navigation was changed: follow the new route; verify the page loads
   - If auth was changed: attempt login/logout; verify redirection
4. Explore adjacent areas for regressions — not just the changed component
5. Check for obvious errors: error messages, broken layouts, missing content

Record: each action taken, what was observed, pass/fail. If the browser cannot start (Chromium not available), mark as `skipped: no browser`.

---

## Step 6: Eval check (conditional)

If the repository has `evals/promptfoo.yaml` **and** the current change modified any of:
- `AGENTS.md` / `agents.md`
- Any file under `skills/`
- Any file under `evals/`

Run: `promptfoo eval --config evals/promptfoo.yaml`

Skip (with reason) if `promptfoo` is not installed or the required API key is not set.

---

## Verification Matrix

Emit this table before handing off to the `review` skill:

```
## Verification Matrix

| Step            | Command / URL                     | Status    | Notes                         |
|-----------------|-----------------------------------|-----------|-------------------------------|
| Build           | npm run build                     | passed    |                               |
| Tests           | npm test                          | passed    | 47/47 tests                   |
| Server start    | npm start (port 3000)             | passed    | /health → 200                 |
| GET /api/users  | http://localhost:3000/api/users   | passed    | 200, returned 3 users         |
| POST /api/items | http://localhost:3000/api/items   | passed    | 201, id present in response   |
| Server stop     | —                                 | passed    |                               |
| E2E suite       | —                                 | skipped   | No playwright/cypress config  |
| Browser UI      | BrowserToolSet (localhost:3000)   | passed    | Home loads, form submits OK   |
| Eval            | —                                 | skipped   | No eval files changed         |
```

---

## Pre-existing Failures

If a step fails on code **not changed by the current task**, verify it was already failing before your changes by stashing your changes, running the command, then restoring. If pre-existing: mark as `pre-existing failure` and continue. Document it in the task summary.

---

## Output

Emit the verification matrix, then hand off to the `review` skill. Fix any `failed` step (that is not pre-existing) before proceeding.

Do not skip this skill. Verification by execution is required before review.
