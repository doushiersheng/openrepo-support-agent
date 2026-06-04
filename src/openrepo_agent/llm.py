from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


class LLMClient(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate text from a chat-style prompt."""


@dataclass(frozen=True)
class DeterministicLLM:
    """Offline fallback used for tests, CI, and inspectable demos."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return ""


@dataclass(frozen=True)
class DeepSeekLLM:
    api_key: str
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    timeout_seconds: int = 30

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        import requests

        response = requests.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]


def build_llm_from_env() -> LLMClient:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return DeterministicLLM()
    return DeepSeekLLM(
        api_key=api_key,
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
