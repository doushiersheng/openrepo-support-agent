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
| Average tool calls | 1.85 |

Task set: `benchmarks/openrepo_support_tasks.jsonl`

The first hardened task set is regression-oriented. It covers:

- project overview
- setup help
- code question
- bug triage
- patch proposal

Next expansion target: 30+ tasks with harder retrieval labels, negative cases,
and human-validated answer rubrics.
