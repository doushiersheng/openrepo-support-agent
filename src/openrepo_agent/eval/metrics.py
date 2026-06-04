from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean


@dataclass(frozen=True)
class EvalMetrics:
    total: int
    intent_accuracy: float
    tool_success_rate: float
    citation_coverage: float
    retrieval_hit_rate: float
    answer_check_pass_rate: float
    monitor_pass_rate: float
    average_tool_calls: float
    failures_by_category: dict[str, int] = field(default_factory=dict)


def safe_rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def summarize_eval(rows: list[dict]) -> EvalMetrics:
    total = len(rows)
    correct_intents = sum(1 for row in rows if row["intent_correct"])
    tool_calls = sum(row["tool_call_count"] for row in rows)
    successful_tool_calls = sum(row["successful_tool_call_count"] for row in rows)
    citation_rows = sum(1 for row in rows if row["citation_count"] > 0)
    retrieval_labeled_rows = [row for row in rows if row["expected_files"]]
    retrieval_hits = sum(1 for row in retrieval_labeled_rows if row["retrieval_hit"])
    answer_labeled_rows = [row for row in rows if row["answer_must_contain"]]
    answer_passes = sum(1 for row in answer_labeled_rows if row["answer_check_passed"])
    monitor_passes = sum(1 for row in rows if row["monitor_status"] == "pass")
    failures_by_category: dict[str, int] = {}
    for row in rows:
        for finding in row["monitor_findings"]:
            category = finding["category"]
            failures_by_category[category] = failures_by_category.get(category, 0) + 1

    return EvalMetrics(
        total=total,
        intent_accuracy=safe_rate(correct_intents, total),
        tool_success_rate=safe_rate(successful_tool_calls, tool_calls),
        citation_coverage=safe_rate(citation_rows, total),
        retrieval_hit_rate=safe_rate(retrieval_hits, len(retrieval_labeled_rows)),
        answer_check_pass_rate=safe_rate(answer_passes, len(answer_labeled_rows)),
        monitor_pass_rate=safe_rate(monitor_passes, total),
        average_tool_calls=mean([row["tool_call_count"] for row in rows]) if rows else 0.0,
        failures_by_category=failures_by_category,
    )
