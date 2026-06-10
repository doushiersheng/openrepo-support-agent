# Evaluation Report

Latest local MVP run:

| Metric | Value |
|---|---:|
| Tasks | 20 |
| Intent accuracy | 100.00% |
| Tool success rate | 100.00% |
| Citation coverage | 100.00% |
| Retrieval hit rate | 100.00% |
| Answer check pass rate | 100.00% |
| Monitor pass rate | 100.00% |
| Expected failure detection rate | 0.00% |
| Average tool calls | 1.85 |

Task set: `benchmarks/openrepo_support_tasks.jsonl`

The first hardened task set is regression-oriented. It covers:

- project overview
- setup help
- code question
- bug triage
- patch proposal

Negative-case run:

| Metric | Value |
|---|---:|
| Tasks | 5 |
| Intent accuracy | 80.00% |
| Tool success rate | 100.00% |
| Citation coverage | 100.00% |
| Retrieval hit rate | 40.00% |
| Answer check pass rate | 40.00% |
| Monitor pass rate | 80.00% |
| Expected failure detection rate | 100.00% |
| Average tool calls | 1.60 |

Task set: `benchmarks/openrepo_negative_cases.jsonl`

Detected failure categories:

- `answer_check_failed`: 3
- `intent_mismatch`: 1
- `retrieval_miss`: 3

Next expansion target: 30+ tasks with harder retrieval labels, more negative
cases, and human-validated answer rubrics.
