from pathlib import Path

from openrepo_agent.agent import OpenRepoSupportAgent


def test_sequential_workflow_answers(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n\nRun with python -m demo.", encoding="utf-8")

    agent = OpenRepoSupportAgent(tmp_path, workflow="sequential")
    response = agent.answer("What does this project do?")

    assert response.intent == "project_overview"
    assert any(event.type == "monitor_inspected" for event in agent.event_log.events)
