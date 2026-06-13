---
name: research
description: 'How to research a codebase, dependency, problem, or industry standards before implementing a change.'
---

# Research

Use this skill when a task requires understanding before implementing — unknown root cause, unfamiliar codebase area, dependency upgrade, new feature design, or when industry standards or best practices are relevant.

## ⚠️ Training Data is Stale — Always Verify Current Information

Your training data has a cutoff date. For anything version-specific, security-related, or evolving (frameworks, libraries, cloud services, security standards, API design conventions), **do not rely on training data alone**.

The current date is available in your context. Use it to reason about what "current" means and to anchor your searches:
- State the current date when searching: *"as of [date], what is the recommended approach for X?"*
- Prefer sources dated within the last 12 months
- Flag any source that appears to predate the current major version of the relevant technology
- When in doubt, search rather than assume

**Use the available tools to retrieve up-to-date information.** See the **Available MCP Tools** section in `AGENTS.md` for the full list. Quick reference:

| Tool | Best for |
|------|----------|
| **context7** | Version-specific library/framework docs (NuGet, npm, PyPI) |
| **tavily** | General web search — best practices, OWASP, release announcements |
| **fetch** / **browser** | Fetching a specific URL |
| **strands-agents** | Strands Agents SDK docs — use when working on a Strands Agents application |

For any library or framework, prefer **context7** first — it returns documentation scoped to the exact version in use rather than whatever your training data remembers.

**Domain-specific skills**: If the project involves Microsoft Agent Framework, also load the `microsoft-agents` skill for MAF conventions, architecture patterns, and API usage. Check the available skills for any other domain-specific skills that may apply.

---

## Codebase Research

When you need to understand the existing code before making a change:

1. **Find the entry point**: locate where the relevant functionality begins (route, event handler, CLI command, public API)
2. **Trace the execution path**: follow the code from entry point through to the affected area; note each layer (controller → service → repository, etc.)
3. **Find similar patterns**: search for existing features that are analogous to what you're building or changing — follow the same structure
4. **Identify shared utilities**: look for base classes, helpers, extension methods, or shared types you should reuse
5. **Check existing dependencies**: before writing a utility, abstraction, or configuration loader, check whether the SDK or framework you are already importing provides it natively. Read the public API surface of relevant packages — do not re-implement what already exists
6. **Check for existing tests**: find tests for the code you're changing — they document expected behaviour and serve as regression anchors

Useful search strategies:
- Search by type/class name, method name, or interface name
- Search by error message text or exception type
- Search by route pattern, event name, or configuration key
- Use `git log --oneline <file>` to understand recent changes if git history is available

## Alternatives Research

You may need to use web search tools to discover current best practices, patterns, or libraries to solve this problem. Make sure your information is up to date. If there are multiple approaches, use subagents to explore each one and compare pros and cons before deciding which to implement.

## Root Cause Research (for bugs)

1. Identify the symptom precisely: what is the actual vs. expected behaviour?
2. Find the code path that produces the symptom
3. Narrow down the condition that triggers the failure — do not fix until the root cause is confirmed
4. Verify by reasoning through the code: "given input X, this code does Y because Z"

## Dependency Research

For version upgrades:
1. **Search for the current latest version** — do not assume your training data reflects the current release
2. Read the official changelog or release notes for every version between old and new
3. Identify: new required configuration, removed or renamed APIs, changed defaults, security fixes
4. Search the codebase for all usages of APIs that changed
5. Note any third-party dependencies that also need updating as a result

For new dependencies:
1. **Search for current alternatives** — the ecosystem may have moved on since your training cutoff
2. Check licensing, maintenance status (last commit date, open issues), and community adoption
3. Read the getting-started documentation for the current version
4. Find examples that match your use case

## Industry Standards & Best Practices Research

When the task involves agentic patterns, API design, security, authentication, data handling, accessibility, performance, or any area governed by evolving standards:

1. **Search for current best practices** using the tools provided. Remember that your training data is outdated
2. Check whether the technology you're working with has released new major versions with changed recommendations since your training cutoff
3. Prefer: official docs > well-maintained open-source guides > community posts
4. Note the publication or last-updated date of any source you rely on

## External Research

When official documentation or migration guides are needed:
- Use web search to find the documentation for the **specific version** in use — docs.microsoft.com, NuGet, npm, PyPI, GitHub releases
- Note the version the documentation applies to
- Flag anything that appears out of date relative to the current version

## Output

> This section applies to **Tier 2, 3, and 4** tasks. Tier 0 (pure Q&A) does not write `research.md`.

Write your research findings to `.openhands/research.md` before proceeding to the next step. This file serves as the handoff artifact — it is the record of what you found, and it is what the user receives if the agent aborts after research.

Use this structure:

```markdown
# Research: <task summary>

**Date**: <current date>

## Summary
One paragraph: what the task requires, what you investigated, and the key conclusion.

## Findings
### <Topic>
- Finding with source and date where applicable

## Sources
| Source | Date | Notes |
|--------|------|-------|
| [Title](url) | YYYY-MM | Prefer sources < 12 months old |

## Patterns & Conventions to Follow
- Pattern observed in existing codebase or documented standard

## Risks & Unknowns
- Any unresolved uncertainty that affects implementation

## Recommendation
Proceed / ABORT: NOT_RECOMMENDED — and why.
```

Rules:
- Always write this file, even if you are about to abort — the user needs to see what you found
- Keep each section concise; this is a summary, not a transcript
- If aborting with `ABORT: NOT_RECOMMENDED`, include your reasoning and alternatives in the Recommendation section before emitting the abort message
