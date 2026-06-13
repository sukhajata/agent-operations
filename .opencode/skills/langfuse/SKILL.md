---
name: langfuse
description: Interact with Langfuse and access its documentation. Use when needing to (1) query or modify Langfuse data programmatically via the CLI — traces, prompts, datasets, scores, sessions, and any other API resource, (2) look up Langfuse documentation, concepts, integration guides, or SDK usage, or (3) understand how any Langfuse feature works. This skill covers CLI-based API access (via npx) and multiple documentation retrieval methods.
allowed-tools:
  - WebFetch(domain:langfuse.com)
  - Bash(curl *langfuse.com/*)
  - Bash(npx langfuse-cli api __schema *)
  - Bash(npx langfuse-cli api * --help *)
  - Bash(npx langfuse-cli api * list *)
  - Bash(npx langfuse-cli api * get *)
  - Bash(bunx langfuse-cli api __schema *)
  - Bash(bunx langfuse-cli api * --help *)
  - Bash(bunx langfuse-cli api * list *)
  - Bash(bunx langfuse-cli api * get *)
---

# Langfuse

This skill helps you use Langfuse effectively: instrumenting applications, migrating prompts, debugging traces, and accessing data programmatically.

## Core Principles

1. **Documentation First**: NEVER implement based on memory. Always fetch current docs before writing code.
2. **CLI for Data Access**: Use `langfuse-cli` when querying/modifying Langfuse data.
3. **Best Practices by Use Case**: Check reference files for use-case-specific guidelines.
4. **Use latest Langfuse versions**: Always use the latest version of Langfuse SDKs/APIs.

## Quick Start

This project already has Langfuse observability configured at `shared/observability/tracing.py`. Usage:

```python
from shared.observability.tracing import configure_tracing

tracer = configure_tracing("exploratory", "agent-1", None, "1.0")
with tracer.trace_llm_call("deepseek/flash", "exploratory", "a1", None, "1.0") as gen:
    response = await model.ainvoke(prompt)
    gen.update(input_tokens=100, output_tokens=50, cost=0.002)
```

## 1. Langfuse API via CLI

```bash
# Discover all available resources
npx langfuse-cli api __schema

# List actions for a resource
npx langfuse-cli api <resource> --help

# Show args/options for a specific action
npx langfuse-cli api <resource> <action> --help
```

### Credentials
```bash
export LANGFUSE_PUBLIC_KEY=pk-lf-...
export LANGFUSE_SECRET_KEY=sk-lf-...
export LANGFUSE_BASE_URL=https://cloud.langfuse.com
```
If using `LANGFUSE_BASE_URL` instead of `LANGFUSE_HOST`, run `export LANGFUSE_HOST="$LANGFUSE_BASE_URL"`.

## 2. Documentation

Three methods to access Langfuse docs:

### 2a. Documentation Index
```bash
curl -s https://langfuse.com/llms.txt
```

### 2b. Fetch Individual Pages as Markdown
```bash
curl -s "https://langfuse.com/docs/observability/overview.md"
curl -s "https://langfuse.com/docs/observability/overview" -H "Accept: text/markdown"
```

### 2c. Search Documentation
```bash
curl -s "https://langfuse.com/api/search-docs?query=<url-encoded-query>"
```

### Documentation Workflow
1. Start with **llms.txt** to orient
2. **Fetch specific pages** when you identify the right one
3. Fall back to **search** when the topic is unclear
