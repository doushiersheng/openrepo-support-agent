from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from openrepo_agent.agent import OpenRepoSupportAgent
from openrepo_agent.events import EventLog
from openrepo_agent.eval.metrics import EvalMetrics, summarize_eval
from openrepo_agent.monitor import MonitorAgent


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip().lower()


def score_expected_files(expected_files: list[str], cited_files: list[str]) -> tuple[bool, list[str]]:
    if not expected_files:
        return False, []
    cited = {normalize_path(path) for path in cited_files}
    matched = []
    for expected in expected_files:
        normalized = normalize_path(expected)
        if normalized in cited:
            matched.append(expected)
    return bool(matched), matched


def score_answer_terms(answer: str, required_terms: list[str]) -> tuple[bool, list[str]]:
    if not required_terms:
        return False, []
    lower_answer = answer.lower()
    matched = [term for term in required_terms if term.lower() in lower_answer]
    return len(matched) == len(required_terms), matched


def load_tasks(path: str | Path) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            task = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_no}: {exc}") from exc
        if "id" not in task or "question" not in task:
            raise ValueError(f"Task line {line_no} must include id and question.")
        tasks.append(task)
    return tasks


class EvalRunner:
    def __init__(self, repo_path: str | Path, monitor: MonitorAgent | None = None) -> None:
        self.repo_path = Path(repo_path)
        self.monitor = monitor or MonitorAgent()

    def run(self, tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], EvalMetrics]:
        rows = []
        for task in tasks:
            event_log = EventLog(run_id=f"eval-{task['id']}")
            agent = OpenRepoSupportAgent(self.repo_path, event_log=event_log)
            response = agent.answer(task["question"])
            expected_intent = task.get("expected_intent")
            report = self.monitor.inspect(response, expected_intent=expected_intent)
            expected_files = task.get("expected_files", [])
            answer_must_contain = task.get("answer_must_contain", [])
            cited_files = [citation.path for citation in response.citations]
            retrieval_hit, matched_files = score_expected_files(expected_files, cited_files)
            answer_check_passed, matched_answer_terms = score_answer_terms(
                response.answer,
                answer_must_contain,
            )
            row = {
                "id": task["id"],
                "question": task["question"],
                "expected_intent": expected_intent,
                "actual_intent": response.intent,
                "intent_correct": expected_intent is None or response.intent == expected_intent,
                "expected_files": expected_files,
                "cited_files": cited_files,
                "matched_files": matched_files,
                "retrieval_hit": retrieval_hit,
                "answer_must_contain": answer_must_contain,
                "matched_answer_terms": matched_answer_terms,
                "answer_check_passed": answer_check_passed,
                "tool_call_count": len(response.tool_results),
                "successful_tool_call_count": sum(1 for result in response.tool_results if result.ok),
                "citation_count": len(response.citations),
                "monitor_status": report.status,
                "monitor_findings": [asdict(finding) for finding in report.findings],
                "answer_preview": response.answer[:500],
                "run_id": response.run_id,
                "events": event_log.to_dict()["events"],
            }
            rows.append(row)
        return rows, summarize_eval(rows)


def write_report(rows: list[dict[str, Any]], metrics: EvalMetrics, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metrics": asdict(metrics),
        "rows": rows,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run OpenRepo Support Agent evaluation.")
    parser.add_argument("--repo", default=".", help="Repository under evaluation.")
    parser.add_argument(
        "--tasks",
        default="benchmarks/openrepo_support_tasks.jsonl",
        help="JSONL task file.",
    )
    parser.add_argument(
        "--output",
        default=".openrepo-agent/eval_report.json",
        help="Where to write the JSON evaluation report.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    tasks = load_tasks(args.tasks)
    rows, metrics = EvalRunner(args.repo).run(tasks)
    write_report(rows, metrics, Path(args.output))

    print(f"Evaluated {metrics.total} tasks")
    print(f"Intent accuracy: {metrics.intent_accuracy:.2%}")
    print(f"Tool success rate: {metrics.tool_success_rate:.2%}")
    print(f"Citation coverage: {metrics.citation_coverage:.2%}")
    print(f"Retrieval hit rate: {metrics.retrieval_hit_rate:.2%}")
    print(f"Answer check pass rate: {metrics.answer_check_pass_rate:.2%}")
    print(f"Monitor pass rate: {metrics.monitor_pass_rate:.2%}")
    print(f"Average tool calls: {metrics.average_tool_calls:.2f}")
    if metrics.failures_by_category:
        print("Failures by category:")
        for category, count in sorted(metrics.failures_by_category.items()):
            print(f"- {category}: {count}")
    print(f"Saved report: {args.output}")


if __name__ == "__main__":
    main()
