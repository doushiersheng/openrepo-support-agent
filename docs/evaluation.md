# Evaluation

The project includes an end-to-end evaluator because support agents fail in
more ways than final-answer correctness.

## Run

```bash
python -m openrepo_agent.eval.runner --repo . --tasks benchmarks/openrepo_support_tasks.jsonl
```

Run the negative-case suite:

```bash
python -m openrepo_agent.eval.runner --repo . \
  --tasks benchmarks/openrepo_negative_cases.jsonl \
  --output .openrepo-agent/negative_eval_report.json
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
- `expected_failure_detection_rate`: percentage of negative cases whose
  expected failure categories were detected
- `average_tool_calls`: average tool calls per task
- `failures_by_category`: monitor and scoring findings grouped by failure type

## Task Schema

```json
{
  "id": "code-001",
  "question": "Where is the command line entrypoint implemented?",
  "expected_intent": "code_question",
  "expected_files": ["src/openrepo_agent/cli.py"],
  "answer_must_contain": ["repo.read_file", "argparse"],
  "expected_failure_categories": []
}
```

`expected_files` is used for retrieval hit rate. `answer_must_contain` is a
deterministic answer rubric for the MVP; a later milestone can add LLM-as-judge
with human spot checks. Negative cases may also provide
`expected_failure_categories`, such as `intent_mismatch`, `retrieval_miss`, or
`answer_check_failed`, so the evaluator can check whether known bad cases were
properly detected.

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

The evaluator also adds scoring-level findings:

- retrieval misses when citations do not include expected files
- answer check failures when the deterministic rubric is not satisfied

This gives the project a measurable baseline before adding a more flexible LLM
judge or online monitor.
