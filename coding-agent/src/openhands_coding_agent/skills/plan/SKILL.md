---
name: plan
description: 'How to write a good implementation plan before making significant code changes.'
---

# Plan

Use this skill when a task requires a plan before implementation — significant scope, multiple files, architectural decisions, or high risk of getting it wrong.

## When to Write a Plan

Write a plan when any of the following are true:
- More than ~5 files will be created or modified
- The change touches shared infrastructure (auth, DI, routing, database schema)
- The approach involves a decision between meaningful alternatives
- The change will be done in phases

## Plan Structure

A good plan has four parts:

### 1. Approach
One paragraph describing the overall approach. State the key design decision and why you chose it over alternatives. Be specific — "add a new service class implementing `IFooService` registered as scoped" is better than "add a service".

### 2. Files
A list of every file to be created or modified, with a one-line description of the change. **Every code change must be paired with the test file that covers it** — include test files in this list explicitly, not as an afterthought:
```
CREATE  src/Features/Foo/FooService.cs         — implements IFooService, handles X and Y
MODIFY  src/Features/Foo/FooController.cs      — inject IFooService, add GET /foo/{id} endpoint
MODIFY  src/Infrastructure/DependencyInjection.cs — register FooService as scoped
CREATE  tests/Features/Foo/FooServiceTests.cs  — unit tests for FooService (new public methods, error paths)
MODIFY  tests/Features/Foo/FooControllerTests.cs — add tests for the new GET /foo/{id} endpoint
```

If a code file has no corresponding test file in this list, that is a gap that must be justified — not silently omitted.

### 3. Risks & Assumptions
- List anything that could go wrong or that you are uncertain about
- State assumptions you are making about requirements or existing behaviour
- Flag any areas where you will need to verify against the database schema, API contract, or external system
- Confirm that no custom implementation is proposed where the existing SDK, framework, or a project dependency already provides the capability

### 4. Verification
How you will confirm the change is correct:
- Which tests cover the new/changed code (reference the test files listed above)
- Any API or UI checks to run (e.g., "start the server and hit /foo endpoint", "navigate to the form and submit")
- What a passing result looks like

## Phased Plans

For large changes, break into phases that can each be verified independently:

```
Phase 1: [description] — verified by [test/build step]
Phase 2: [description] — verified by [test/build step]
Phase 3: [description] — verified by [test/build step]
```

Implement and verify one phase at a time. Do not start the next phase until the current one builds and tests pass.

## Parallelism

When writing the plan, identify which steps are independent of each other — these are candidates for parallel sub-agent execution. Annotate them explicitly so the execute phase can delegate efficiently.

**In a phased plan**, mark phases or steps that can run concurrently:

```
Phase 1 [parallel]:
  SPAWN research-api:   read the existing API layer and note patterns
  SPAWN research-tests: read the existing test suite and note coverage gaps
Phase 2 [sequential, depends on Phase 1]:
  Implement new feature following discovered patterns
Phase 3 [parallel]:
  SPAWN implement-tests: write unit tests for the new service
  SPAWN implement-docs:  update OpenAPI/README for the new endpoint
Phase 4 [sequential, depends on Phase 3]:
  Verify: full build and test suite
```

**Rules for parallel annotation:**
- Steps that read different parts of the codebase are almost always parallelisable
- Steps that write to the same file must be sequential
- Tests and implementation for different modules can run in parallel
- Any step that depends on the output of another must be sequential

The execute phase will use `TaskToolSet` to spawn sub-agents and delegate parallel steps. Design the plan to maximise concurrency.

## Persisting the Plan

Always write the completed plan to a file before starting execution:

- **Tier 3**: write to `.openhands/plan.md`
- **Tier 4**: write to `.openhands/tier4-plan.md`

Create the `.openhands/` directory if it does not exist. This directory is gitignored.

The lifecycle of these files — when they are deleted, and how the Tier 4 re-invocation flow works — is defined in the workflow tiers in `AGENTS.md`.
