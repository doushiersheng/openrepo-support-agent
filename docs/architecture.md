# Architecture

OpenRepo Support Agent is organized around explicit runtime primitives rather
than opaque agent magic.

## Runtime Flow

1. The user submits a repository support question.
2. `IntentRouter` classifies the request into an operational intent.
3. `OpenRepoSupportAgent` runs the sequential, multi-agent, or LangGraph
   workflow.
4. The workflow selects a small tool plan for that intent.
5. `ToolRegistry` executes tools and logs every call.
6. The agent composes an answer with citations.
7. Optional DeepSeek synthesis can rewrite the final answer using only tool
   context.
8. Risky tools create pending approvals instead of executing immediately.
9. `MonitorAgent` inspects the run for failures and safety gaps.
10. `SQLiteStore` persists sessions, turns, events, memory items, and approvals.

## Why This Shape

The goal is to make every agent decision inspectable:

- intent routing can be tested
- retrieval quality can be measured
- tool failures can be attributed
- future human approval can be inserted before risky actions

## Evaluation Loop

`openrepo_agent.eval.runner` runs JSONL tasks end to end. For each task it
captures the answer, intent, tool results, citations, event log, and monitor
findings. The summary metrics are:

- intent accuracy
- tool success rate
- citation coverage
- monitor pass rate
- average tool calls
- failures by category

## Multi-Agent Workflow

The `multi_agent` workflow keeps the runtime deterministic but makes role
boundaries visible in the event log:

- `RouterAgent` routes the request and records confidence/rationale.
- `RepoResearchAgent` selects repository retrieval and citation gathering.
- `IssueTriageAgent` handles setup, bug, and issue routing.
- `PatchPlannerAgent` prepares patch proposals before any write action.
- `SafetyReviewerAgent` checks whether approval-gated tools are involved.
- `MonitorAgent` inspects the final answer, citations, and tool results.

Each role writes a `multi_agent_step` event. This makes the collaboration trace
auditable without requiring multiple paid LLM calls.

## LangGraph Mapping

The current modules map cleanly to a LangGraph workflow, and the CLI supports
this path with `--workflow langgraph`:

- Router node: `IntentRouter`
- Planner node: intent-specific tool plan
- Tool node: `ToolRegistry`
- Answer node: response composer
- Monitor node: failed run analyzer
- Approval node: write/command gate

## LLM Boundary

The LLM is only used for final answer synthesis when `--use-llm` is provided.
Routing, tool execution, citations, monitoring, and evaluation remain explicit
runtime steps. This keeps the system debuggable and prevents the portfolio from
depending on a paid API key.

## Session Memory

When a `session_id` is provided, the agent persists each turn in SQLite and
extracts long-term memory items from the user question:

- user environment, such as Windows, Python version, Docker, or conda
- observed errors, such as `ModuleNotFoundError`
- attempted commands, such as `python -m openrepo_agent.cli`

Memory is intentionally extracted from user-provided text rather than retrieved
answer snippets. This avoids memory contamination where repo examples or test
fixtures are accidentally treated as things the user actually tried.

## Human Approval

Risky tools, such as `repo.write_file`, are registered with
`requires_approval=True`. Patch requests can create a row in the `approvals`
table containing the tool name and arguments. The tool is executed only when a
human runs the CLI with `--approve <id>`.

This separates proposal from execution:

- the agent can suggest or prepare a write action
- SQLite stores the pending action for auditability
- explicit human approval executes the tool
- repeated approval attempts are rejected after the first decision
