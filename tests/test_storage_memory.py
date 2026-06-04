from pathlib import Path

from openrepo_agent.agent import OpenRepoSupportAgent
from openrepo_agent.memory import MemoryExtractor
from openrepo_agent.storage import SQLiteStore


def test_memory_extractor_finds_environment_and_errors() -> None:
    items = MemoryExtractor().extract(
        "On Windows with Python 3.12 I get ModuleNotFoundError when running python -m demo",
        "Try pip install -e .",
    )

    assert ("environment", "Windows") in items
    assert any(kind == "error" and "ModuleNotFoundError" in value for kind, value in items)
    assert any(kind == "attempted_command" and value.startswith("python -m demo") for kind, value in items)


def test_sqlite_store_saves_turn_and_memory(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n\nRun with python -m demo.", encoding="utf-8")
    store = SQLiteStore(tmp_path / "agent.db")
    store.ensure_session("s1", repo)

    agent = OpenRepoSupportAgent(repo, session_id="s1", store=store)
    response = agent.answer("On Windows, how do I run this project?")

    turns = store.load_recent_turns("s1")
    memory = store.load_memory_items("s1")

    assert turns
    assert turns[0]["run_id"] == response.run_id
    assert any(item["kind"] == "environment" for item in memory)


def test_persisted_memory_uses_user_question_not_answer_context(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text(
        "# Demo\n\nRun with python -m demo and install with pip install -e .",
        encoding="utf-8",
    )
    store = SQLiteStore(tmp_path / "agent.db")

    agent = OpenRepoSupportAgent(repo, session_id="s1", store=store)
    agent.answer("On Windows I see ModuleNotFoundError")

    memory = store.load_memory_items("s1")
    values = {item["value"] for item in memory}
    assert "Windows" in values
    assert all("python -m demo" not in value for value in values)
