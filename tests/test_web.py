from pathlib import Path

from openrepo_agent.agent import OpenRepoSupportAgent
from openrepo_agent.web import response_to_demo_payload


def test_web_demo_payload_exposes_agent_trace(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n\nRun with python -m demo.", encoding="utf-8")
    (tmp_path / "cli.py").write_text("def main():\n    print('demo')\n", encoding="utf-8")

    agent = OpenRepoSupportAgent(tmp_path, workflow="multi_agent")
    payload = response_to_demo_payload(
        agent,
        "Where is the command line entrypoint implemented?",
    )

    assert payload["intent"] == "code_question"
    assert payload["tool_results"]
    assert payload["citations"]
    assert any(step["role"] == "RouterAgent" for step in payload["role_trace"])
    assert payload["monitor"]["status"] == "pass"
