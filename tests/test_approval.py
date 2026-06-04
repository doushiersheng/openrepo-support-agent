from pathlib import Path

from openrepo_agent.agent import OpenRepoSupportAgent
from openrepo_agent.storage import SQLiteStore


def test_patch_request_creates_pending_approval(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    store = SQLiteStore(tmp_path / "agent.db")

    agent = OpenRepoSupportAgent(repo, session_id="s1", store=store)
    response = agent.answer("Please add a note file for this patch")

    approvals = store.list_approvals("s1")
    assert approvals
    assert approvals[0]["tool_name"] == "repo.write_file"
    assert any(result.name == "approval.request" for result in response.tool_results)


def test_approval_executes_write_file_once(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    store = SQLiteStore(tmp_path / "agent.db")

    agent = OpenRepoSupportAgent(repo, session_id="s1", store=store)
    agent.answer("Please create a patch note file")
    approval_id = store.list_approvals("s1")[0]["id"]

    result = agent.approve(approval_id)
    second = agent.approve(approval_id)

    assert result.ok
    assert (repo / "scratch" / "approved_patch_note.md").exists()
    assert not second.ok
    assert store.get_approval(approval_id)["status"] == "approved"
