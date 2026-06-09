# Changelog

## 0.1.0

Initial portfolio release.

- Local repo indexing with citations
- Local Web Demo for inspecting intent, role trace, tool calls, citations,
  monitor status, and event logs
- Intent routing across overview, setup, code, bug, issue, and patch workflows
- MCP-style tool registry
- Sequential and optional LangGraph workflow runtimes
- Role-based multi-agent workflow with auditable routing, research, patch
  planning, safety review, and monitoring steps
- Optional DeepSeek-compatible final answer synthesis
- SQLite persistence for sessions, turns, events, memory, and approvals
- Conversation memory for user environment, errors, and attempted commands
- Human approval workflow for risky file writes
- Rule-based monitor for failed-session attribution
- Hardened 20-task benchmark with label isolation
- Metrics for intent accuracy, tool success, citation coverage, retrieval hit,
  answer checks, monitor pass rate, and average tool calls
