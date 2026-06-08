from pathlib import Path

from openrepo_agent.agent import OpenRepoSupportAgent


def test_sequential_workflow_answers(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n\nRun with python -m demo.", encoding="utf-8")

    agent = OpenRepoSupportAgent(tmp_path, workflow="sequential")
    response = agent.answer("What does this project do?")

    assert response.intent == "project_overview"
    assert any(event.type == "monitor_inspected" for event in agent.event_log.events)


def test_multi_agent_workflow_records_role_trace(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n\nRun with python -m demo.", encoding="utf-8")
    (tmp_path / "cli.py").write_text("def main():\n    print('demo')\n", encoding="utf-8")

    agent = OpenRepoSupportAgent(tmp_path, workflow="multi_agent")
    response = agent.answer("Where is the command line entrypoint implemented?")

    role_events = [event for event in agent.event_log.events if event.type == "multi_agent_step"]
    roles = {event.payload["role"] for event in role_events}

    assert response.intent == "code_question"
    assert "Multi-agent trace:" in response.answer
    assert {"RouterAgent", "RepoResearchAgent", "ToolExecutorAgent", "SafetyReviewerAgent", "MonitorAgent"} <= roles
