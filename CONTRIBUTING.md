# Contributing

Thanks for taking a look at OpenRepo Support Agent.

## Local Setup

```bash
python -m pip install -e .
python -m pytest
```

## Run the Benchmark

```bash
python -m openrepo_agent.eval.runner --repo .
```

Benchmark tasks live under `benchmarks/`, and the repo indexer ignores that
directory by default to avoid label leakage during self-evaluation.

## Design Rules

- Keep the default runtime deterministic and runnable without API keys.
- Use optional LLM calls only for bounded answer synthesis.
- Preserve citations when adding answer logic.
- Do not execute risky tools without the approval workflow.
- Extract long-term memory only from user-provided text.

## API Keys

Do not commit real API keys. Use `.env.example` as the template and keep local
secrets in `.env`.
