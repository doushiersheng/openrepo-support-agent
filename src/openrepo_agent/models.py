from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Citation:
    path: str
    line_start: int
    line_end: int
    snippet: str


@dataclass(frozen=True)
class SearchHit:
    path: str
    score: float
    line_start: int
    line_end: int
    snippet: str


@dataclass
class RepoDocument:
    path: str
    absolute_path: Path
    kind: str
    text: str
    lines: list[str]


@dataclass(frozen=True)
class ToolResult:
    name: str
    ok: bool
    content: str
    citations: list[Citation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResponse:
    question: str
    intent: str
    answer: str
    citations: list[Citation]
    tool_results: list[ToolResult]
    run_id: str
