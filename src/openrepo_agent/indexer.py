from __future__ import annotations

import re
from pathlib import Path

from .models import RepoDocument, SearchHit


DEFAULT_INCLUDE_SUFFIXES = {
    ".md",
    ".rst",
    ".txt",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
}

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "benchmarks",
    "examples",
    ".mypy_cache",
    ".pytest_cache",
    ".openrepo-agent",
}


def classify_file(path: Path) -> str:
    name = path.name.lower()
    suffix = path.suffix.lower()
    parts = {part.lower() for part in path.parts}
    if name.startswith("readme"):
        return "readme"
    if "docs" in parts or suffix in {".md", ".rst"}:
        return "docs"
    if "test" in parts or name.startswith("test_") or name.endswith("_test.py"):
        return "test"
    if suffix in {".json", ".toml", ".yaml", ".yml", ".ini", ".cfg"}:
        return "config"
    return "code"


class RepoIndex:
    def __init__(self, repo_path: Path, documents: list[RepoDocument]) -> None:
        self.repo_path = repo_path
        self.documents = documents

    @classmethod
    def build(cls, repo_path: str | Path) -> "RepoIndex":
        root = Path(repo_path).resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Repository path does not exist or is not a directory: {root}")

        documents: list[RepoDocument] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relative_parts = path.relative_to(root).parts
            if any(part in DEFAULT_IGNORE_DIRS for part in relative_parts):
                continue
            if path.suffix.lower() not in DEFAULT_INCLUDE_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if len(text) > 250_000:
                continue
            relative = path.relative_to(root).as_posix()
            documents.append(
                RepoDocument(
                    path=relative,
                    absolute_path=path,
                    kind=classify_file(path.relative_to(root)),
                    text=text,
                    lines=text.splitlines(),
                )
            )
        return cls(root, documents)

    def overview(self) -> str:
        counts: dict[str, int] = {}
        for doc in self.documents:
            counts[doc.kind] = counts.get(doc.kind, 0) + 1
        important = [
            doc.path
            for doc in self.documents
            if doc.kind in {"readme", "config"} or doc.path.endswith("cli.py")
        ][:12]
        counts_text = ", ".join(f"{kind}: {count}" for kind, count in sorted(counts.items()))
        important_text = "\n".join(f"- {path}" for path in important) or "- No key files found"
        return f"Indexed {len(self.documents)} files ({counts_text}).\nKey files:\n{important_text}"

    def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        terms = [term for term in re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", query.lower()) if len(term) > 1]
        if not terms:
            terms = [query.lower()]
        normalized_query = query.replace("\\", "/").lower()
        hits: list[SearchHit] = []
        for doc in self.documents:
            lower_lines = [line.lower() for line in doc.lines]
            best_score = 0.0
            best_line = 0
            for line_no, line in enumerate(lower_lines):
                score = sum(1 for term in terms if term in line)
                if doc.kind in {"readme", "docs"}:
                    score *= 1.2
                if score > best_score:
                    best_score = float(score)
                    best_line = line_no
            path_score = sum(1 for term in terms if term in doc.path.lower()) * 1.5
            if doc.path.lower() in normalized_query:
                path_score += 20.0
            if path_score > best_score:
                best_score = path_score
                best_line = 0
            if best_score <= 0:
                continue
            start = max(0, best_line - 2)
            end = min(len(doc.lines), best_line + 3)
            snippet = "\n".join(doc.lines[start:end]).strip()
            hits.append(
                SearchHit(
                    path=doc.path,
                    score=best_score,
                    line_start=start + 1,
                    line_end=end,
                    snippet=snippet,
                )
            )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]

    def get_document(self, relative_path: str) -> RepoDocument | None:
        normalized = relative_path.replace("\\", "/")
        for doc in self.documents:
            if doc.path == normalized:
                return doc
        return None
