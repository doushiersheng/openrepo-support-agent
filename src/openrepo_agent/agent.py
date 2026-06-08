from __future__ import annotations

from pathlib import Path

from .events import EventLog
from .indexer import RepoIndex
from .intent import IntentRouter
from .llm import LLMClient, build_llm_from_env
from .memory import ConversationMemory, MemoryExtractor
from .models import AgentResponse, Citation, ToolResult
from .storage import SQLiteStore
from .tools.registry import ToolRegistry
from .tools.repo_tools import RepoTools
from .workflow import build_workflow


class OpenRepoSupportAgent:
    def __init__(
        self,
        repo_path: str | Path,
        event_log: EventLog | None = None,
        workflow: str = "sequential",
        use_llm: bool = False,
        llm: LLMClient | None = None,
        session_id: str | None = None,
        store: SQLiteStore | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.index = RepoIndex.build(self.repo_path)
        self.event_log = event_log or EventLog()
        self.router = IntentRouter()
        self.registry = ToolRegistry(self.event_log)
        self.workflow_name = workflow
        self.use_llm = use_llm
        self.llm = llm or build_llm_from_env()
        self.session_id = session_id
        self.store = store
        self.memory_extractor = MemoryExtractor()
        self.memory = ConversationMemory(
            self.store.load_memory_items(session_id) if self.store and session_id else []
        )
        if self.store and self.session_id:
            self.store.ensure_session(self.session_id, self.repo_path)
        RepoTools(self.index).register(self.registry)

    def answer(self, question: str) -> AgentResponse:
        response = build_workflow(self, self.workflow_name).run(question)
        self._persist_response(response)
        return response

    def _run_tools(self, question: str, intent: str) -> list[ToolResult]:
        if intent == "project_overview":
            return [
                self.registry.call("repo.overview"),
                self.registry.call("repo.search_code", query=question, limit=4),
            ]
        if intent == "setup_help":
            return [
                self.registry.call(
                    "repo.search_code",
                    query=f"install setup run {question} {self._memory_query_terms()}",
                    limit=5,
                ),
                self.registry.call("issue.triage", question=question),
            ]
        if intent == "bug_triage":
            return [
                self.registry.call("issue.triage", question=question),
                self.registry.call(
                    "repo.search_code",
                    query=f"{question} {self._memory_query_terms()}",
                    limit=5,
                ),
            ]
        if intent == "patch_request":
            results = [
                self.registry.call("repo.search_code", query=question, limit=5),
                self.registry.call("patch.propose", question=question),
            ]
            approval = self._maybe_create_patch_approval(question)
            if approval:
                results.append(approval)
            return results
        if intent == "issue_triage":
            return [
                self.registry.call("issue.triage", question=question),
                self.registry.call("repo.search_code", query=question, limit=3),
            ]
        results = [
            self.registry.call(
                "repo.search_code",
                query=f"{question} cli main entrypoint command function class",
                limit=5,
            )
        ]
        explicit_path = self._find_explicit_path_file(question)
        if explicit_path:
            results.append(self.registry.call("repo.read_file", path=explicit_path, max_lines=240))
            return results
        entrypoint = self._find_entrypoint_file(question)
        if entrypoint:
            results.append(self.registry.call("repo.read_file", path=entrypoint, max_lines=120))
        return results

    def _compose_answer(
        self,
        question: str,
        intent: str,
        tool_results: list[ToolResult],
    ) -> str:
        successful = [result for result in tool_results if result.ok]
        if not successful:
            errors = "; ".join(result.content for result in tool_results)
            return f"I could not complete the request. Tool errors: {errors}"

        if intent == "project_overview":
            overview = successful[0].content
            answer = (
                "I indexed the repository and found the main support context.\n\n"
                f"{overview}\n\n"
                "Use a more specific question to inspect setup, code paths, or issue triage."
            )
            return self._maybe_enhance_with_llm(question, intent, tool_results, answer)
        if intent == "setup_help":
            answer = (
                "This looks like a setup or environment support request. I searched the "
                "repo for install/run/configuration context and prepared triage questions.\n\n"
                + self._join_tool_content(successful)
            )
            return self._maybe_enhance_with_llm(question, intent, tool_results, answer)
        if intent == "bug_triage":
            answer = (
                "This looks like a bug triage request. I classified the issue first, then "
                "searched the repository for likely relevant code or docs.\n\n"
                + self._join_tool_content(successful)
            )
            return self._maybe_enhance_with_llm(question, intent, tool_results, answer)
        if intent == "patch_request":
            answer = (
                "This looks like a patch request. I searched for candidate files and drafted "
                "a safe patch workflow. The MVP does not write files without approval.\n\n"
                + self._join_tool_content(successful)
            )
            return self._maybe_enhance_with_llm(question, intent, tool_results, answer)
        if intent == "issue_triage":
            answer = (
                "This looks like an issue triage request. I suggested a label and follow-up "
                "questions, then attached repo context that may help route it.\n\n"
                + self._join_tool_content(successful)
            )
            return self._maybe_enhance_with_llm(question, intent, tool_results, answer)
        answer = (
            "I searched the repository for code and documentation related to your question.\n\n"
            + self._join_tool_content(successful)
        )
        return self._maybe_enhance_with_llm(question, intent, tool_results, answer)

    def _join_tool_content(self, tool_results: list[ToolResult]) -> str:
        sections = []
        for result in tool_results:
            sections.append(f"### {result.name}\n{result.content}")
        return "\n\n".join(sections)

    def _collect_citations(self, tool_results: list[ToolResult]) -> list[Citation]:
        citations: list[Citation] = []
        seen: set[tuple[str, int, int]] = set()
        for result in tool_results:
            for citation in result.citations:
                key = (citation.path, citation.line_start, citation.line_end)
                if key in seen:
                    continue
                seen.add(key)
                citations.append(citation)
        return citations

    def _maybe_enhance_with_llm(
        self,
        question: str,
        intent: str,
        tool_results: list[ToolResult],
        fallback_answer: str,
    ) -> str:
        if not self.use_llm:
            return fallback_answer

        context = self._join_tool_content([result for result in tool_results if result.ok])
        system_prompt = (
            "You are OpenRepo Support Agent. Answer using only the provided tool "
            "context. Preserve file citations and avoid claiming that files were "
            "modified. Be concise and operational."
        )
        user_prompt = (
            f"Intent: {intent}\n"
            f"Question: {question}\n\n"
            f"{self.memory.to_prompt_block()}\n\n"
            f"Tool context:\n{context}\n\n"
            f"Deterministic fallback answer:\n{fallback_answer}"
        )
        try:
            enhanced = self.llm.generate(system_prompt, user_prompt).strip()
        except Exception as exc:
            self.event_log.record("llm_error", error=str(exc))
            return fallback_answer
        if not enhanced:
            return fallback_answer
        self.event_log.record("llm_enhanced_answer", provider=self.llm.__class__.__name__)
        return enhanced

    def _maybe_create_patch_approval(self, question: str) -> ToolResult | None:
        if not self.store or not self.session_id:
            return None
        if not any(term in question.lower() for term in ("write", "create", "add", "生成", "创建", "写入")):
            return None
        path = "scratch/approved_patch_note.md"
        content = (
            "# Approved Patch Note\n\n"
            "This file is created only after human approval.\n\n"
            f"Original request: {question}\n"
        )
        approval_id = self.store.create_approval(
            session_id=self.session_id,
            run_id=self.event_log.run_id,
            tool_name="repo.write_file",
            args={"path": path, "content": content},
        )
        self.event_log.record(
            "approval_created",
            approval_id=approval_id,
            tool="repo.write_file",
            path=path,
        )
        return ToolResult(
            name="approval.request",
            ok=True,
            content=(
                f"Created pending approval #{approval_id} for repo.write_file -> {path}. "
                "Run the CLI with --approve to execute it."
            ),
            metadata={"approval_id": approval_id, "tool": "repo.write_file", "path": path},
        )

    def approve(self, approval_id: int) -> ToolResult:
        if not self.store:
            return ToolResult(
                name="approval.execute",
                ok=False,
                content="Approval execution requires a SQLite store.",
            )
        approval = self.store.get_approval(approval_id)
        if approval is None:
            return ToolResult(
                name="approval.execute",
                ok=False,
                content=f"Approval not found: {approval_id}",
            )
        if approval["status"] != "pending":
            return ToolResult(
                name="approval.execute",
                ok=False,
                content=f"Approval #{approval_id} is already {approval['status']}.",
                metadata={"approval": approval},
            )
        tool = self.registry.get(approval["tool_name"])
        if tool is None or not tool.requires_approval:
            result = ToolResult(
                name="approval.execute",
                ok=False,
                content="Approval references an unknown or non-approval tool.",
            )
            self.store.mark_approval_decided(approval_id, "rejected", {"error": result.content})
            return result

        self.event_log.record(
            "approval_execute",
            approval_id=approval_id,
            tool=tool.name,
            args=approval["args"],
        )
        result = tool.handler(**approval["args"])
        status = "approved" if result.ok else "failed"
        self.store.mark_approval_decided(
            approval_id,
            status,
            {"ok": result.ok, "content": result.content, "metadata": result.metadata},
        )
        self.event_log.record(
            "approval_result",
            approval_id=approval_id,
            status=status,
            content_preview=result.content[:500],
        )
        return result

    def _memory_query_terms(self) -> str:
        values = [item["value"] for item in self.memory.items if item["kind"] in {"environment", "error"}]
        return " ".join(values[:8])

    def _persist_response(self, response: AgentResponse) -> None:
        if not self.store or not self.session_id:
            return
        items = self.memory_extractor.extract(response.question, "")
        self.event_log.record("memory_extracted", count=len(items))
        self.store.save_turn(self.session_id, response, self.event_log)
        self.store.add_memory_items(self.session_id, response.run_id, items)
        self.memory = ConversationMemory(self.store.load_memory_items(self.session_id))

    def _find_entrypoint_file(self, question: str) -> str | None:
        lower = question.lower()
        if not any(term in lower for term in ("entrypoint", "cli", "command", "入口", "命令")):
            return None
        for doc in self.index.documents:
            if doc.path.endswith("cli.py"):
                return doc.path
        for doc in self.index.documents:
            if doc.path.endswith("main.py"):
                return doc.path
        return None

    def _find_explicit_path_file(self, question: str) -> str | None:
        normalized = question.replace("\\", "/")
        for doc in self.index.documents:
            if doc.path in normalized:
                return doc.path
        return None
