# Optional Real LLM Synthesis

OpenRepo Support Agent is designed to run without a model key by default. The
deterministic runtime handles intent routing, tool execution, citations,
approval gates, event logging, memory, monitoring, and evaluation.

When `DEEPSEEK_API_KEY` is set, the runtime can call a DeepSeek/OpenAI-compatible
chat completion endpoint for final answer synthesis. The LLM does not replace
the agent runtime. It receives the tool context and fallback answer, then
rewrites the final response while the same tools, citations, and audit events
remain visible.

## Why The LLM Is Optional

The project keeps the core runtime deterministic for three reasons:

- tests and benchmark runs are reproducible without network access
- routing, tool calls, citations, and approvals remain inspectable
- the LLM is bounded by retrieved tool context instead of acting as an opaque
  controller

This mirrors a production-friendly agent pattern: use deterministic control
flow for safety and observability, then use a model for language synthesis where
it adds value.

## Configure DeepSeek

Copy `.env.example` and set your own key in the shell environment. Do not commit
real keys.

Windows PowerShell:

```powershell
$env:DEEPSEEK_API_KEY="sk-..."
$env:DEEPSEEK_MODEL="deepseek-chat"
$env:DEEPSEEK_BASE_URL="https://api.deepseek.com"
```

macOS/Linux:

```bash
export DEEPSEEK_API_KEY="sk-..."
export DEEPSEEK_MODEL="deepseek-chat"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
```

Install the optional HTTP dependency:

```bash
python -m pip install -e ".[llm]"
```

Run a real LLM-enhanced answer:

```bash
python -m openrepo_agent.cli --repo . --use-llm \
  "How do I install and run this project?"
```

Run the Web Demo with LLM synthesis:

```bash
openrepo-agent-web --repo . --use-llm
```

## What To Verify

The output should still include:

- deterministic intent routing
- MCP-style tool calls
- file citations
- monitor status
- event log entries

When the model call succeeds, the event log includes:

```json
{
  "type": "llm_enhanced_answer",
  "payload": {
    "provider": "DeepSeekLLM"
  }
}
```

If the model call fails, the runtime records `llm_error` and falls back to the
deterministic answer. Tool execution and evaluation still work.

## Sample Output

See `examples/deepseek_llm_demo_output.json` for a sanitized example of the
expected response surface. The sample intentionally does not include any API
key or raw provider response.
