from openrepo_agent.llm import DeterministicLLM


def test_deterministic_llm_returns_empty_string() -> None:
    assert DeterministicLLM().generate("system", "user") == ""
