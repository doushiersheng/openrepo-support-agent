from pathlib import Path

from openrepo_agent.indexer import RepoIndex


def test_indexer_finds_readme(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n\nRun with python -m demo.", encoding="utf-8")
    (tmp_path / "demo.py").write_text("def main():\n    return 'ok'\n", encoding="utf-8")

    index = RepoIndex.build(tmp_path)

    assert len(index.documents) == 2
    hits = index.search("run python")
    assert hits
    assert hits[0].path == "README.md"
