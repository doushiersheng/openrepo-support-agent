# Persistence and Memory

OpenRepo Support Agent can persist multi-turn support sessions in SQLite.

## Run

```bash
python -m openrepo_agent.cli --repo . --session-id demo \
  --show-memory "On Windows with Python 3.12 I get ModuleNotFoundError"
```

The default database path is:

```text
.openrepo-agent/openrepo.sqlite
```

## Schema

- `sessions`: session id, repo path, timestamps
- `turns`: question, intent, answer, citations, tool results
- `events`: auditable runtime events for each run
- `memory_items`: extracted long-term memory
- `approvals`: pending/approved/rejected risky tool actions

## Memory Types

- `environment`: OS, Python/Node versions, Docker, conda, pip
- `error`: exception names, tracebacks, or user-described failures
- `attempted_command`: commands the user says they ran

## Anti-Contamination Rule

Long-term memory is extracted from user-provided text only. The agent does not
extract memory from retrieved repository snippets or its own generated answer,
because that can pollute the session with examples the user never actually ran.

## Approval Flow

```bash
python -m openrepo_agent.cli --repo . --session-id demo \
  "Please create a patch note file for this safe patch workflow"
python -m openrepo_agent.cli --repo . --session-id demo --list-approvals
python -m openrepo_agent.cli --repo . --approve 1
```

Approvals keep high-risk actions auditable and prevent silent repository
mutation.
