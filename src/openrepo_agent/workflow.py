from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from .models import AgentResponse, Citation, ToolResult
from .monitor import MonitorAgent, MonitorReport

if TYPE_CHECKING:
    from .agent import OpenRepoSupportAgent


class WorkflowState(TypedDict, total=False):
    question: str
    intent: str
    tool_results: list[ToolResult]
    citations: list[Citation]
    answer: str
    response: AgentResponse
    monitor_report: MonitorReport


class SequentialWorkflow:
    def __init__(self, agent: "OpenRepoSupportAgent") -> None:
        self.agent = agent

    def run(self, question: str) -> AgentResponse:
        self.agent.event_log.record("user_question", question=question)
        self.agent.event_log.record(
            "memory_loaded",
            item_count=len(self.agent.memory.items),
        )
        intent = self.agent.router.route(question)
        self.agent.event_log.record(
            "intent_routed",
            intent=intent.name,
            confidence=intent.confidence,
            rationale=intent.rationale,
            workflow="sequential",
        )

        tool_results = self.agent._run_tools(question, intent.name)
        answer = self.agent._compose_answer(question, intent.name, tool_results)
        citations = self.agent._collect_citations(tool_results)
        response = AgentResponse(
            question=question,
            intent=intent.name,
            answer=answer,
            citations=citations,
            tool_results=tool_results,
            run_id=self.agent.event_log.run_id,
        )
        report = MonitorAgent().inspect(response)
        self.agent.event_log.record(
            "monitor_inspected",
            status=report.status,
            findings=[finding.category for finding in report.findings],
        )
        self.agent.event_log.record(
            "answer_composed",
            answer_preview=answer[:500],
            citation_count=len(citations),
        )
        return response


class LangGraphWorkflow:
    def __init__(self, agent: "OpenRepoSupportAgent") -> None:
        self.agent = agent
        self._graph = self._build_graph()

    def run(self, question: str) -> AgentResponse:
        state = self._graph.invoke({"question": question})
        return state["response"]

    def _build_graph(self) -> Any:
        try:
            from langgraph.graph import END, StateGraph
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise RuntimeError("LangGraph is not installed. Use workflow='sequential'.") from exc

        graph = StateGraph(WorkflowState)
        graph.add_node("route", self._route)
        graph.add_node("tools", self._tools)
        graph.add_node("answer", self._answer)
        graph.add_node("monitor", self._monitor)
        graph.set_entry_point("route")
        graph.add_edge("route", "tools")
        graph.add_edge("tools", "answer")
        graph.add_edge("answer", "monitor")
        graph.add_edge("monitor", END)
        return graph.compile()

    def _route(self, state: WorkflowState) -> WorkflowState:
        question = state["question"]
        self.agent.event_log.record("user_question", question=question)
        self.agent.event_log.record(
            "memory_loaded",
            item_count=len(self.agent.memory.items),
        )
        intent = self.agent.router.route(question)
        self.agent.event_log.record(
            "intent_routed",
            intent=intent.name,
            confidence=intent.confidence,
            rationale=intent.rationale,
            workflow="langgraph",
        )
        return {"intent": intent.name}

    def _tools(self, state: WorkflowState) -> WorkflowState:
        return {
            "tool_results": self.agent._run_tools(
                state["question"],
                state["intent"],
            )
        }

    def _answer(self, state: WorkflowState) -> WorkflowState:
        tool_results = state["tool_results"]
        answer = self.agent._compose_answer(state["question"], state["intent"], tool_results)
        citations = self.agent._collect_citations(tool_results)
        response = AgentResponse(
            question=state["question"],
            intent=state["intent"],
            answer=answer,
            citations=citations,
            tool_results=tool_results,
            run_id=self.agent.event_log.run_id,
        )
        self.agent.event_log.record(
            "answer_composed",
            answer_preview=answer[:500],
            citation_count=len(citations),
        )
        return {"answer": answer, "citations": citations, "response": response}

    def _monitor(self, state: WorkflowState) -> WorkflowState:
        report = MonitorAgent().inspect(state["response"])
        self.agent.event_log.record(
            "monitor_inspected",
            status=report.status,
            findings=[finding.category for finding in report.findings],
        )
        return {"monitor_report": report}


def build_workflow(agent: "OpenRepoSupportAgent", workflow: str) -> SequentialWorkflow | LangGraphWorkflow:
    if workflow == "sequential":
        return SequentialWorkflow(agent)
    if workflow == "langgraph":
        return LangGraphWorkflow(agent)
    raise ValueError(f"Unsupported workflow: {workflow}")
