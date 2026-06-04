# Demo Script

Use these commands for a quick portfolio walkthrough.

## 1. Code-Aware Support

```bash
python -m openrepo_agent.cli --repo . \
  "Where is the command line entrypoint implemented?"
```

What to point out:

- intent is `code_question`
- the agent calls `repo.search_code`
- explicit code questions read `src/openrepo_agent/cli.py`
- answers include file citations

## 2. Multi-Turn Memory

```bash
python -m openrepo_agent.cli --repo . --session-id demo --show-memory \
  "On Windows with Python 3.12 I get ModuleNotFoundError"
python -m openrepo_agent.cli --repo . --session-id demo --show-memory \
  "I already tried python -m openrepo_agent.cli. What should I check next?"
```

What to point out:

- SQLite stores turns and memory items
- memory tracks user environment, errors, and attempted commands
- memory is extracted from user text only

## 3. Human Approval

```bash
python -m openrepo_agent.cli --repo . --session-id demo \
  "Please create a patch note file for this safe patch workflow"
python -m openrepo_agent.cli --repo . --session-id demo --list-approvals
python -m openrepo_agent.cli --repo . --approve 1
```

What to point out:

- patch request creates a pending approval
- file write is not executed silently
- approval state is persisted in SQLite

## 4. Hardened Benchmark

```bash
python -m openrepo_agent.eval.runner --repo .
```

What to point out:

- labels are under `benchmarks/`
- `benchmarks/` is ignored by the repo indexer
- metrics include retrieval hit and answer check pass rate
