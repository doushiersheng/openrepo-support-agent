from __future__ import annotations

from pathlib import Path

from openrepo_agent.indexer import RepoIndex
from openrepo_agent.models import Citation, ToolResult
from openrepo_agent.tools.registry import Tool, ToolRegistry


def citation_from_hit(path: str, line_start: int, line_end: int, snippet: str) -> Citation:
    return Citation(path=path, line_start=line_start, line_end=line_end, snippet=snippet)


class RepoTools:
    def __init__(self, index: RepoIndex) -> None:
        self.index = index

    def register(self, registry: ToolRegistry) -> None:
        registry.register(
            Tool(
                name="repo.overview",
                description="Summarize indexed repository structure.",
                requires_approval=False,
                handler=self.overview,
            )
        )
        registry.register(
            Tool(
                name="repo.search_code",
                description="Search docs and source code for relevant snippets.",
                requires_approval=False,
                handler=self.search_code,
            )
        )
        registry.register(
            Tool(
                name="repo.read_file",
                description="Read a repository file by relative path.",
                requires_approval=False,
                handler=self.read_file,
            )
        )
        registry.register(
            Tool(
                name="issue.triage",
                description="Classify a support issue and suggest follow-up questions.",
                requires_approval=False,
                handler=self.triage_issue,
            )
        )
        registry.register(
            Tool(
                name="patch.propose",
                description="Draft a safe patch plan. Does not write files.",
                requires_approval=False,
                handler=self.propose_patch,
            )
        )
        registry.register(
            Tool(
                name="repo.write_file",
                description="Write a repository file. Approval required.",
                requires_approval=True,
                handler=self.write_file,
            )
        )

    def overview(self) -> ToolResult:
        return ToolResult(name="repo.overview", ok=True, content=self.index.overview())

    def search_code(self, query: str, limit: int = 5) -> ToolResult:
        hits = self.index.search(query, limit=limit)
        if not hits:
            return ToolResult(name="repo.search_code", ok=True, content="No relevant files found.")
        citations = [
            citation_from_hit(hit.path, hit.line_start, hit.line_end, hit.snippet)
            for hit in hits
        ]
        content = "\n\n".join(
            f"{hit.path}:{hit.line_start}-{hit.line_end}\n{hit.snippet}" for hit in hits
        )
        return ToolResult(
            name="repo.search_code",
            ok=True,
            content=content,
            citations=citations,
            metadata={"hit_count": len(hits)},
        )

    def read_file(self, path: str, max_lines: int = 80) -> ToolResult:
        doc = self.index.get_document(path)
        if doc is None:
            return ToolResult(name="repo.read_file", ok=False, content=f"File not found: {path}")
        lines = doc.lines[:max_lines]
        snippet = "\n".join(lines)
        citation = Citation(
            path=doc.path,
            line_start=1,
            line_end=len(lines),
            snippet=snippet,
        )
        return ToolResult(
            name="repo.read_file",
            ok=True,
            content=snippet,
            citations=[citation],
            metadata={"truncated": len(doc.lines) > max_lines},
        )

    def triage_issue(self, question: str) -> ToolResult:
        lower = question.lower()
        if any(token in lower for token in ("error", "exception", "traceback", "报错", "失败")):
            label = "bug"
            next_questions = [
                "What command produced the error?",
                "What is the full traceback?",
                "Which OS and Python/Node version are you using?",
            ]
        elif any(token in lower for token in ("feature", "support", "需求", "希望")):
            label = "feature-request"
            next_questions = [
                "What user workflow would this feature unlock?",
                "Is there an existing workaround?",
            ]
        elif any(token in lower for token in ("install", "setup", "env", "安装", "配置")):
            label = "environment"
            next_questions = [
                "Which dependency manager are you using?",
                "Can you share the environment variables and versions?",
            ]
        else:
            label = "usage-question"
            next_questions = [
                "What goal are you trying to accomplish?",
                "Which docs or examples have you already tried?",
            ]
        content = "Suggested label: {label}\nFollow-up questions:\n{questions}".format(
            label=label,
            questions="\n".join(f"- {item}" for item in next_questions),
        )
        return ToolResult(
            name="issue.triage",
            ok=True,
            content=content,
            metadata={"label": label, "next_questions": next_questions},
        )

    def propose_patch(self, question: str) -> ToolResult:
        hits = self.index.search(question, limit=3)
        citations = [
            citation_from_hit(hit.path, hit.line_start, hit.line_end, hit.snippet)
            for hit in hits
        ]
        candidate_files = ", ".join(hit.path for hit in hits) or "No candidate files found"
        content = (
            "Patch proposal only; no files were modified.\n"
            f"Candidate files: {candidate_files}\n"
            "Suggested workflow:\n"
            "1. Confirm the intended behavior and add a failing test.\n"
            "2. Modify the smallest relevant function or config path.\n"
            "3. Run the targeted test before widening the change.\n"
            "4. Request human approval before applying any file write."
        )
        return ToolResult(
            name="patch.propose",
            ok=True,
            content=content,
            citations=citations,
            metadata={"candidate_files": [hit.path for hit in hits]},
        )

    def write_file(self, path: str, content: str) -> ToolResult:
        relative = Path(path)
        if relative.is_absolute() or ".." in relative.parts:
            return ToolResult(
                name="repo.write_file",
                ok=False,
                content="Refusing to write outside the repository.",
            )
        target = (self.index.repo_path / relative).resolve()
        if not str(target).startswith(str(self.index.repo_path.resolve())):
            return ToolResult(
                name="repo.write_file",
                ok=False,
                content="Refusing to write outside the repository.",
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult(
            name="repo.write_file",
            ok=True,
            content=f"Wrote {path}",
            metadata={"path": path, "bytes": len(content.encode("utf-8"))},
        )
