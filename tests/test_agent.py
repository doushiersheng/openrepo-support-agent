from pathlib import Path

from openrepo_agent.agent import OpenRepoSupportAgent


def test_agent_answers_with_citations(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Demo\n\nInstall with pip and run the CLI with python -m demo.",
        encoding="utf-8",
    )
    (tmp_path / "demo.py").write_text("def main():\n    print('hello')\n", encoding="utf-8")

    agent = OpenRepoSupportAgent(tmp_path)
    response = agent.answer("How do I install and run this project?")

    assert response.intent == "setup_help"
    assert response.citations
    assert any(result.name == "repo.search_code" for result in response.tool_results)
    assert agent.event_log.events
