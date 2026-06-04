from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConversationMemory:
    items: list[dict] = field(default_factory=list)

    def to_prompt_block(self) -> str:
        if not self.items:
            return "No prior session memory."
        grouped: dict[str, list[str]] = {}
        for item in self.items:
            grouped.setdefault(item["kind"], []).append(item["value"])
        lines = ["Prior session memory:"]
        for kind, values in sorted(grouped.items()):
            lines.append(f"- {kind}:")
            for value in values[:8]:
                lines.append(f"  - {value}")
        return "\n".join(lines)


class MemoryExtractor:
    ENV_PATTERNS = (
        r"\bwindows\b",
        r"\bmacos\b",
        r"\blinux\b",
        r"\bpython\s*[\d.]+",
        r"\bnode\s*[\d.]+",
        r"\bconda\b",
        r"\bpip\b",
        r"\bdocker\b",
    )

    ERROR_PATTERNS = (
        r"[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception):?[^\n。]*",
        r"traceback[^\n。]*",
        r"报错[^\n。]*",
        r"失败[^\n。]*",
    )

    COMMAND_PATTERN = (
        r"(?:python(?!\s*\d)|pip|conda|npm|pnpm|yarn|pytest|docker)\s+[^\n。；;]+"
    )

    def extract(self, question: str, answer: str = "") -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        source = f"{question}\n{answer}"

        for pattern in self.ENV_PATTERNS:
            for match in re.finditer(pattern, source, flags=re.IGNORECASE):
                items.append(("environment", match.group(0).strip()))

        for pattern in self.ERROR_PATTERNS:
            for match in re.finditer(pattern, source, flags=re.IGNORECASE):
                items.append(("error", match.group(0).strip()))

        for match in re.finditer(self.COMMAND_PATTERN, source, flags=re.IGNORECASE):
            items.append(("attempted_command", match.group(0).strip()))

        return self._dedupe(items)

    def _dedupe(self, items: list[tuple[str, str]]) -> list[tuple[str, str]]:
        seen: set[tuple[str, str]] = set()
        deduped: list[tuple[str, str]] = []
        for kind, value in items:
            normalized = (kind, re.sub(r"\s+", " ", value).strip())
            if len(normalized[1]) < 3 or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped
