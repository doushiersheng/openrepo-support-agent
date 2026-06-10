from pathlib import Path

from openrepo_agent.eval.runner import (
    EvalRunner,
    detected_failure_categories,
    load_tasks,
    score_answer_terms,
    score_expected_files,
)


def test_eval_runner_summarizes_tasks(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Demo\n\nInstall with pip. Run with python -m demo.",
        encoding="utf-8",
    )
    (tmp_path / "demo.py").write_text("def main():\n    return 'ok'\n", encoding="utf-8")
    tasks = [
        {
            "id": "setup",
            "question": "How do I install and run this?",
            "expected_intent": "setup_help",
            "expected_files": ["README.md"],
            "answer_must_contain": ["issue.triage"],
        }
    ]

    rows, metrics = EvalRunner(tmp_path).run(tasks)

    assert len(rows) == 1
    assert metrics.total == 1
    assert metrics.intent_accuracy == 1.0
    assert metrics.tool_success_rate == 1.0
    assert metrics.retrieval_hit_rate == 1.0
    assert metrics.answer_check_pass_rate == 1.0


def test_load_tasks(tmp_path: Path) -> None:
    task_file = tmp_path / "tasks.jsonl"
    task_file.write_text('{"id":"a","question":"What is this?"}\n', encoding="utf-8")

    tasks = load_tasks(task_file)

    assert tasks == [{"id": "a", "question": "What is this?"}]


def test_score_expected_files() -> None:
    hit, matched = score_expected_files(["src/app.py"], ["README.md", "src/app.py"])
    assert hit
    assert matched == ["src/app.py"]


def test_score_answer_terms_requires_all_terms() -> None:
    passed, matched = score_answer_terms("Use issue.triage and repo.search_code", ["issue.triage", "missing"])
    assert not passed
    assert matched == ["issue.triage"]


def test_detected_failure_categories_combines_monitor_and_scoring_failures() -> None:
    categories = detected_failure_categories(
        [{"category": "intent_mismatch"}],
        retrieval_labeled=True,
        retrieval_hit=False,
        answer_labeled=True,
        answer_check_passed=False,
    )

    assert categories == ["answer_check_failed", "intent_mismatch", "retrieval_miss"]


def test_eval_runner_tracks_expected_failure_detection(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n\nRun with python -m demo.", encoding="utf-8")
    tasks = [
        {
            "id": "negative",
            "question": "What does this project do?",
            "expected_intent": "bug_triage",
            "expected_files": ["README.md"],
            "answer_must_contain": ["Key files"],
            "expected_failure_categories": ["intent_mismatch"],
        }
    ]

    rows, metrics = EvalRunner(tmp_path).run(tasks)

    assert "intent_mismatch" in rows[0]["detected_failure_categories"]
    assert metrics.expected_failure_detection_rate == 1.0
    assert metrics.failures_by_category["intent_mismatch"] == 1
