from __future__ import annotations

from dataclasses import dataclass, field

from .models import AgentResponse


@dataclass(frozen=True)
class MonitorFinding:
    category: str
    severity: str
    message: str


@dataclass(frozen=True)
class MonitorReport:
    status: str
    findings: list[MonitorFinding] = field(default_factory=list)


class MonitorAgent:
    """Rule-based monitor for failed-session attribution.

    This is deliberately deterministic for the portfolio MVP. It gives us an
    inspectable baseline before replacing or augmenting it with an LLM judge.
    """

    def inspect(
        self,
        response: AgentResponse,
        expected_intent: str | None = None,
    ) -> MonitorReport:
        findings: list[MonitorFinding] = []

        if expected_intent and response.intent != expected_intent:
            findings.append(
                MonitorFinding(
                    category="intent_mismatch",
                    severity="high",
                    message=(
                        f"Expected intent '{expected_intent}' but router returned "
                        f"'{response.intent}'."
                    ),
                )
            )

        failed_tools = [result.name for result in response.tool_results if not result.ok]
        if failed_tools:
            findings.append(
                MonitorFinding(
                    category="tool_error",
                    severity="high",
                    message=f"Tool failures: {', '.join(failed_tools)}.",
                )
            )

        if not response.citations and response.intent != "issue_triage":
            findings.append(
                MonitorFinding(
                    category="missing_citation",
                    severity="medium",
                    message="Answer has no repository citation; retrieval may have failed.",
                )
            )

        if response.intent == "patch_request":
            tool_names = {result.name for result in response.tool_results}
            if "patch.propose" not in tool_names:
                findings.append(
                    MonitorFinding(
                        category="missing_safety_step",
                        severity="high",
                        message="Patch request did not go through patch proposal workflow.",
                    )
                )

        if response.intent == "bug_triage":
            tool_names = {result.name for result in response.tool_results}
            if "issue.triage" not in tool_names:
                findings.append(
                    MonitorFinding(
                        category="missing_triage_step",
                        severity="medium",
                        message="Bug triage request did not call issue.triage.",
                    )
                )

        status = "pass" if not findings else "review"
        return MonitorReport(status=status, findings=findings)
