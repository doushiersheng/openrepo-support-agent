from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Intent:
    name: str
    confidence: float
    rationale: str


class IntentRouter:
    """A deterministic first-pass router for inspectable MVP behavior."""

    RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "patch_request",
            (
                "fix",
                "patch",
                "change",
                "modify",
                "add test",
                "修改",
                "修复",
                "补丁",
                "测试",
            ),
        ),
        (
            "bug_triage",
            (
                "bug",
                "error",
                "exception",
                "traceback",
                "fail",
                "失败",
                "报错",
                "cannot",
                "can't",
            ),
        ),
        (
            "setup_help",
            (
                "install",
                "setup",
                "run",
                "start",
                "启动",
                "安装",
                "配置",
                "configure",
                "依赖",
                "environment",
                "env",
            ),
        ),
        (
            "issue_triage",
            (
                "issue",
                "label",
                "triage",
                "feature request",
                "需求",
                "分流",
                "分类",
            ),
        ),
        (
            "code_question",
            (
                "where",
                "function",
                "class",
                "entrypoint",
                "api",
                "实现",
                "函数",
                "类",
                "入口",
                "代码",
            ),
        ),
    )

    def route(self, question: str) -> Intent:
        normalized = re.sub(r"\s+", " ", question.lower())
        if self._looks_like_code_question(normalized):
            return Intent(
                name="code_question",
                confidence=0.88,
                rationale="Matched explicit code-inspection pattern.",
            )
        for intent_name, keywords in self.RULES:
            for keyword in keywords:
                if keyword.lower() in normalized:
                    return Intent(
                        name=intent_name,
                        confidence=0.82,
                        rationale=f"Matched keyword '{keyword}' for {intent_name}.",
                    )
        return Intent(
            name="project_overview",
            confidence=0.65,
            rationale="No specialized intent matched; defaulting to overview.",
        )

    def _looks_like_code_question(self, normalized: str) -> bool:
        if re.search(r"\bsrc/[a-z0-9_/\-.]+\.(py|js|ts|tsx|jsx)\b", normalized):
            return True
        if any(token in normalized for token in ("where is", "implemented", "class ", "function ")):
            return True
        if "how does" in normalized and any(
            token in normalized
            for token in (
                "persistence",
                "evaluation",
                "compute",
                "prevent",
                "repo.",
                "store ",
                "approval",
                "memory",
            )
        ):
            return True
        return False
