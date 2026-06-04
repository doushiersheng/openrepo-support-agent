# Evaluation

The project includes an end-to-end evaluator because support agents fail in
more ways than final-answer correctness.

## Run

```bash
python -m openrepo_agent.eval.runner --repo . --tasks benchmarks/openrepo_support_tasks.jsonl
```

## Metrics

- `intent_accuracy`: whether routing matched the expected task intent
- `tool_success_rate`: percentage of tool calls that completed successfully
- `citation_coverage`: percentage of answers with at least one repo citation
- `retrieval_hit_rate`: percentage of labeled tasks whose citations include an
  expected file
- `answer_check_pass_rate`: percentage of labeled tasks whose answer contains
  all required rubric terms
- `monitor_pass_rate`: percentage of runs without monitor findings
- `average_tool_calls`: average tool calls per task
- `failures_by_category`: monitor findings grouped by failure type

## Task Schema

```json
{
  "id": "code-001",
  "question": "Where is the command line entrypoint implemented?",
  "expected_intent": "code_question",
  "expected_files": ["src/openrepo_agent/cli.py"],
  "answer_must_contain": ["repo.read_file", "argparse"]
}
```

`expected_files` is used for retrieval hit rate. `answer_must_contain` is a
deterministic answer rubric for the MVP; a later milestone can add LLM-as-judge
with human spot checks.

## Benchmark Isolation

Benchmark labels live under `benchmarks/`, and the repo indexer ignores that
directory by default. This prevents the agent from retrieving hidden labels
such as `expected_files` or `answer_must_contain` during self-evaluation.

## Monitor Findings

The current `MonitorAgent` is rule-based and deterministic. It flags:

- intent mismatches
- tool errors
- missing citations
- patch requests that skip the patch proposal workflow
- bug reports that skip issue triage

This gives the project a measurable baseline before adding a more flexible LLM
judge or online monitor.
