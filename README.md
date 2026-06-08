# OpenRepo Support Agent

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-17%20passed-brightgreen)](#evaluation)
[![Benchmark](https://img.shields.io/badge/benchmark-20%20tasks-brightgreen)](#evaluation)

An end-to-end agent system for open-source project support. It indexes a local
repository, routes user intent, calls MCP-style tools, keeps an auditable event
log, and answers with file citations.

This is built as a portfolio-grade agent runtime, not a one-prompt chatbot. The
core path is deterministic and inspectable, while the multi-agent workflow,
LangGraph, and DeepSeek are optional layers.

Real LLM calls are optional. The default mode is deterministic and works
without an API key. If `DEEPSEEK_API_KEY` is set, the CLI can use DeepSeek to
enhance the final answer while keeping the same tool and audit trail.

## Why This Project

Open-source support is a realistic agent scenario: users ask setup questions,
report errors, request issue triage, and sometimes need code-aware patch
guidance. A useful support agent needs more than RAG:

- intent routing across support, code, bug, issue, and patch workflows
- repo-aware retrieval with file citations
- multi-turn memory for user environment, errors, and attempted commands
- approval gates for risky tools
- evaluation that measures routing, retrieval, answer checks, tools, and monitor
  findings

## Current Results

Hardened benchmark: `benchmarks/openrepo_support_tasks.jsonl`

| Metric | Value |
|---|---:|
| Tasks | 20 |
| Intent accuracy | 100.00% |
| Tool success rate | 100.00% |
| Citation coverage | 100.00% |
| Retrieval hit rate | 100.00% |
| Answer check pass rate | 100.00% |
| Monitor pass rate | 100.00% |
| Average tool calls | 1.85 |

## Features

- Repo indexing for README, docs, source code, config, and tests
- Intent routing for project overview, setup, code questions, bug reports,
  issue triage, and patch requests
- MCP-style `ToolRegistry` with typed tool inputs and consistent outputs
- Code search, file reading, issue triage, and patch suggestion tools
- Event audit log for every route decision and tool call
- Evaluation runner for end-to-end support tasks
- Rule-based monitor for failed-session attribution
- Multi-agent workflow with router, repository researcher, issue triage,
  patch planner, safety reviewer, and monitor roles
- Optional LangGraph workflow runtime
- Optional DeepSeek/OpenAI-compatible LLM answer enhancement
- SQLite-backed sessions, turns, event logs, and memory items
- Conversation memory for user environment, errors, and attempted commands
- Human approval workflow for risky tools such as file writes
- CLI demo that can run against any local repository

## Demo

Code-aware question:

```bash
python -m openrepo_agent.cli --repo . \
  "Where is the command line entrypoint implemented?"
```

Expected behavior:

- routes to `code_question`
- calls `repo.search_code`
- detects and reads `src/openrepo_agent/cli.py`
- returns citations for the relevant files

Multi-turn memory:

```bash
python -m openrepo_agent.cli --repo . --session-id demo --show-memory \
  "On Windows with Python 3.12 I get ModuleNotFoundError"
python -m openrepo_agent.cli --repo . --session-id demo --show-memory \
  "I already tried python -m openrepo_agent.cli. What should I check next?"
```

Approval-gated write:

```bash
python -m openrepo_agent.cli --repo . --session-id demo \
  "Please create a patch note file for this safe patch workflow"
python -m openrepo_agent.cli --repo . --session-id demo --list-approvals
python -m openrepo_agent.cli --repo . --approve 1
```

## Quick Start

```bash
cd openrepo-support-agent
python -m pip install -e .
python -m openrepo_agent.cli --repo . "What does this project do?"
python -m openrepo_agent.cli --repo . "Where is the command line entrypoint?"
python -m openrepo_agent.cli --repo . "I get an import error when running the CLI. Triage this issue."
```

The CLI prints the detected intent, answer, citations, tool calls, and audit
events. By default it writes run logs to `.openrepo-agent/runs/`.

Run through LangGraph:

```bash
python -m openrepo_agent.cli --repo . --workflow langgraph "Where is the command line entrypoint?"
```

Run the role-based multi-agent workflow:

```bash
python -m openrepo_agent.cli --repo . --workflow multi_agent \
  "Where is the command line entrypoint implemented?"
```

This prints the same answer/citation surface while the event log records each
role decision as `multi_agent_step`.

Use DeepSeek for the final answer synthesis:

```bash
$env:DEEPSEEK_API_KEY="sk-..."
python -m openrepo_agent.cli --repo . --use-llm "How do I install and run this project?"
```

Do not commit real API keys. Use `.env.example` as the template.

Persist a multi-turn support session:

```bash
python -m openrepo_agent.cli --repo . --session-id demo \
  --show-memory "On Windows with Python 3.12 I get ModuleNotFoundError"
python -m openrepo_agent.cli --repo . --session-id demo \
  --show-memory "I already tried python -m openrepo_agent.cli. What should I check next?"
```

Session data is stored in `.openrepo-agent/openrepo.sqlite` by default.

Create and approve a safe write action:

```bash
python -m openrepo_agent.cli --repo . --session-id demo \
  "Please create a patch note file for this safe patch workflow"
python -m openrepo_agent.cli --repo . --session-id demo --list-approvals
python -m openrepo_agent.cli --repo . --approve 1
```

Patch requests can create pending approvals, but file writes do not execute
until an explicit approval command runs.

Run the end-to-end evaluation suite:

```bash
python -m openrepo_agent.eval.runner --repo . --tasks benchmarks/openrepo_support_tasks.jsonl
```

The evaluator reports intent accuracy, tool success rate, citation coverage,
retrieval hit rate, answer check pass rate, monitor pass rate, and average tool
calls. It writes a detailed JSON report to `.openrepo-agent/eval_report.json`.

See the current summary in `docs/eval_report.md`.

## Architecture

```mermaid
flowchart TD
    U["User question"] --> R["Intent Router"]
    R --> P["Support Agent"]
    P --> W["Sequential, Multi-Agent, or LangGraph Workflow"]
    W --> G["Router / Research / Triage / Patch / Safety Roles"]
    G --> T["Tool Registry"]
    T --> S["repo.search_code"]
    T --> F["repo.read_file"]
    T --> I["issue.triage"]
    T --> X["patch.propose"]
    S --> A["Answer Composer"]
    F --> A
    I --> A
    X --> A
    A --> O["Optional LLM Synthesis"]
    O --> H["Human Approval Gate"]
    H --> M["Monitor Agent"]
    M --> L["SQLite Store + Eval Report + Event Audit Log"]
```

The default path uses deterministic routing and retrieval so behavior is
inspectable. The multi-agent workflow keeps the same tools but records explicit
role decisions:

- RouterAgent routes the request.
- RepoResearchAgent gathers repository context and citations.
- IssueTriageAgent handles setup, bug, and issue classification.
- PatchPlannerAgent prepares patch proposals without writing files.
- SafetyReviewerAgent checks whether risky tools need approval.
- MonitorAgent inspects the final response and event trail.

The optional LangGraph workflow uses the same primitives:

- Router node
- Planner node
- Tool execution node
- Human approval node
- Monitor node
- Evaluation node

The current code supports `--workflow multi_agent` and `--workflow langgraph`.
The sequential path remains the default so tests and demos are reproducible.

## Evaluation

The benchmark task file is JSONL:

```json
{"id":"setup-001","question":"How do I install and run this project locally?","expected_intent":"setup_help"}
```

Each run records:

- expected vs actual intent
- expected files vs cited files
- required answer terms vs matched answer terms
- tool calls and tool success rate
- citation count
- monitor status
- failure categories such as `intent_mismatch`, `tool_error`, and
  `missing_citation`

This makes the project easier to discuss in interviews: the agent is not only
able to answer, it can also measure and explain where it fails.

## What Makes It Non-Toy

- Hidden benchmark labels live under `benchmarks/`, and the indexer ignores
  them to avoid evaluation contamination.
- Long-term memory is extracted only from user input, not retrieved snippets or
  generated answers.
- Risky tools create pending approvals instead of mutating files silently.
- The default runtime is deterministic, so tests and benchmark runs are
  reproducible without API keys.
- Optional LLM synthesis is bounded by tool context and does not replace the
  explicit runtime steps.

## Documentation

- [Demo script](docs/demo.md)
- [Architecture](docs/architecture.md)
- [Evaluation](docs/evaluation.md)
- [Evaluation report](docs/eval_report.md)
- [Persistence and memory](docs/persistence.md)
- [Roadmap](docs/roadmap.md)

## Project Layout

```text
openrepo-support-agent/
  src/openrepo_agent/
    agent.py
    cli.py
    events.py
    indexer.py
    intent.py
    llm.py
    memory.py
    models.py
    monitor.py
    storage.py
    workflow.py
    eval/
      metrics.py
      runner.py
    tools/
      registry.py
      repo_tools.py
  docs/
    architecture.md
    evaluation.md
    eval_report.md
    persistence.md
    roadmap.md
  benchmarks/
    openrepo_support_tasks.jsonl
  tests/
```

## Design Notes

The project is built around a simple rule: an agent system should be observable
before it is clever. Every route decision and tool call is logged with inputs,
outputs, and citations. This makes later evaluation and monitoring possible.
Long-term memory is extracted only from user-provided text, not retrieved
answer context, to avoid contaminating memory with snippets from the repo.
Risky tools use pending approvals, so the agent can propose actions without
silently mutating the repository.

## Roadmap

- Add command execution with approval and sandbox policy
- Add FastAPI service and minimal web UI
- Expand benchmark to 30+ tasks with negative cases
