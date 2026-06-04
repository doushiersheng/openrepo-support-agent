from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from openrepo_agent.events import EventLog
from openrepo_agent.models import ToolResult

ToolHandler = Callable[..., ToolResult]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    requires_approval: bool
    handler: ToolHandler


class ToolRegistry:
    def __init__(self, event_log: EventLog) -> None:
        self.event_log = event_log
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def call(self, name: str, **kwargs: Any) -> ToolResult:
        if name not in self._tools:
            result = ToolResult(name=name, ok=False, content=f"Unknown tool: {name}")
            self.event_log.record("tool_error", tool=name, error=result.content)
            return result

        tool = self._tools[name]
        self.event_log.record(
            "tool_call",
            tool=name,
            requires_approval=tool.requires_approval,
            input=kwargs,
        )
        if tool.requires_approval:
            result = ToolResult(
                name=name,
                ok=False,
                content="Tool requires human approval in this MVP.",
                metadata={"approval_required": True},
            )
            self.event_log.record("tool_blocked_for_approval", tool=name)
            return result

        try:
            result = tool.handler(**kwargs)
        except Exception as exc:  # pragma: no cover - defensive audit path
            result = ToolResult(name=name, ok=False, content=str(exc))
            self.event_log.record("tool_error", tool=name, error=str(exc))
            return result

        self.event_log.record(
            "tool_result",
            tool=name,
            ok=result.ok,
            content_preview=result.content[:500],
            citations=[citation.path for citation in result.citations],
        )
        return result
