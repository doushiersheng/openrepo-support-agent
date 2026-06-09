from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .agent import OpenRepoSupportAgent
from .storage import SQLiteStore


DEFAULT_QUESTIONS = [
    "What does this project do?",
    "Where is the command line entrypoint implemented?",
    "I get an import error when running the CLI. Triage this issue.",
    "Please create a patch note file for this safe patch workflow",
]


def response_to_demo_payload(agent: OpenRepoSupportAgent, question: str) -> dict[str, Any]:
    response = agent.answer(question)
    events = agent.event_log.to_dict()["events"]
    role_trace = [
        {
            "role": event["payload"].get("role", "UnknownAgent"),
            "decision": event["payload"].get("decision", ""),
            "metadata": {
                key: value
                for key, value in event["payload"].items()
                if key not in {"role", "decision"}
            },
        }
        for event in events
        if event["type"] == "multi_agent_step"
    ]
    monitor_events = [event for event in events if event["type"] == "monitor_inspected"]

    return {
        "run_id": response.run_id,
        "question": response.question,
        "intent": response.intent,
        "answer": response.answer,
        "citations": [asdict(citation) for citation in response.citations],
        "tool_results": [
            {
                "name": result.name,
                "ok": result.ok,
                "content": result.content,
                "citations": [asdict(citation) for citation in result.citations],
                "metadata": result.metadata,
            }
            for result in response.tool_results
        ],
        "role_trace": role_trace,
        "monitor": monitor_events[-1]["payload"] if monitor_events else {},
        "events": events,
    }


class DemoServer:
    def __init__(
        self,
        repo_path: str | Path,
        workflow: str = "multi_agent",
        use_llm: bool = False,
        db_path: str | Path = ".openrepo-agent/openrepo.sqlite",
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.workflow = workflow
        self.use_llm = use_llm
        self.db_path = Path(db_path)

    def handle_question(self, question: str, session_id: str | None = "web-demo") -> dict[str, Any]:
        store = SQLiteStore(self.db_path) if session_id else None
        agent = OpenRepoSupportAgent(
            self.repo_path,
            workflow=self.workflow,
            use_llm=self.use_llm,
            session_id=session_id,
            store=store,
        )
        return response_to_demo_payload(agent, question)


def build_handler(demo: DemoServer) -> type[BaseHTTPRequestHandler]:
    class OpenRepoDemoHandler(BaseHTTPRequestHandler):
        server_version = "OpenRepoDemo/0.1"

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self._send_html(INDEX_HTML)
                return
            if path == "/api/examples":
                self._send_json({"questions": DEFAULT_QUESTIONS})
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path != "/api/ask":
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return

            try:
                content_length = int(self.headers.get("content-length", "0"))
                body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(body) if body else {}
                question = str(payload.get("question", "")).strip()
                session_id = str(payload.get("session_id", "web-demo")).strip() or None
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                self._send_json({"error": f"Invalid request: {exc}"}, HTTPStatus.BAD_REQUEST)
                return

            if not question:
                self._send_json({"error": "question is required"}, HTTPStatus.BAD_REQUEST)
                return

            try:
                result = demo.handle_question(question, session_id=session_id)
            except Exception as exc:  # pragma: no cover - server safety net
                self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json(result)

        def log_message(self, format: str, *args: Any) -> None:
            print("%s - %s" % (self.address_string(), format % args))

        def _send_html(self, html: str) -> None:
            encoded = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(
            self,
            payload: dict[str, Any],
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return OpenRepoDemoHandler


def run_server(
    repo_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    workflow: str = "multi_agent",
    use_llm: bool = False,
    db_path: str | Path = ".openrepo-agent/openrepo.sqlite",
) -> None:
    demo = DemoServer(repo_path, workflow=workflow, use_llm=use_llm, db_path=db_path)
    server = ThreadingHTTPServer((host, port), build_handler(demo))
    url = f"http://{host}:{port}"
    print(f"OpenRepo web demo running at {url}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the OpenRepo Support Agent web demo.")
    parser.add_argument("--repo", default=".", help="Path to the local repository to inspect.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    parser.add_argument(
        "--workflow",
        choices=["sequential", "multi_agent", "langgraph"],
        default="multi_agent",
        help="Workflow runtime to use in the demo.",
    )
    parser.add_argument("--use-llm", action="store_true", help="Use DEEPSEEK_API_KEY for answer synthesis.")
    parser.add_argument(
        "--db",
        default=".openrepo-agent/openrepo.sqlite",
        help="SQLite database path for demo sessions and approvals.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_server(
        args.repo,
        host=args.host,
        port=args.port,
        workflow=args.workflow,
        use_llm=args.use_llm,
        db_path=args.db,
    )


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenRepo Support Agent Demo</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #1e2329;
      --muted: #65717f;
      --line: #d8dee6;
      --accent: #1769aa;
      --ok: #19734d;
      --warn: #9a5b00;
      --bad: #a12a2a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }
    header {
      padding: 24px 32px 18px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1 {
      margin: 0 0 8px;
      font-size: 28px;
      line-height: 1.15;
      font-weight: 760;
    }
    .subhead {
      max-width: 900px;
      margin: 0;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.5;
    }
    main {
      display: grid;
      grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
      gap: 18px;
      padding: 18px;
      max-width: 1440px;
      margin: 0 auto;
    }
    section, aside {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    aside {
      padding: 16px;
      height: fit-content;
      position: sticky;
      top: 12px;
    }
    label {
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 650;
    }
    textarea, input {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
      font: inherit;
      background: #fff;
      color: var(--ink);
    }
    textarea {
      min-height: 128px;
      resize: vertical;
      line-height: 1.45;
    }
    button {
      border: 1px solid #155d96;
      border-radius: 6px;
      padding: 10px 12px;
      font: inherit;
      font-weight: 700;
      background: var(--accent);
      color: white;
      cursor: pointer;
    }
    button.secondary {
      width: 100%;
      margin-top: 8px;
      text-align: left;
      background: #fff;
      color: var(--ink);
      border-color: var(--line);
      font-weight: 600;
    }
    button:disabled { opacity: 0.62; cursor: wait; }
    .row {
      display: flex;
      gap: 10px;
      align-items: center;
      margin-top: 12px;
    }
    .row input { flex: 1; }
    .workspace {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 14px;
    }
    .panel {
      padding: 16px;
    }
    .panel h2 {
      margin: 0 0 12px;
      font-size: 16px;
      line-height: 1.2;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .stat {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      min-height: 76px;
      background: #fbfcfd;
    }
    .stat span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }
    .stat strong {
      font-size: 17px;
      overflow-wrap: anywhere;
    }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      margin: 0;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: 12px;
      line-height: 1.5;
    }
    .answer {
      line-height: 1.55;
      color: #26313d;
    }
    .list {
      display: grid;
      gap: 8px;
    }
    .item {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fbfcfd;
    }
    .item-title {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
      font-weight: 700;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 12px;
      font-weight: 700;
      background: #e9f2fb;
      color: #135a91;
      white-space: nowrap;
    }
    .pill.ok { background: #e6f3ed; color: var(--ok); }
    .pill.bad { background: #f8e8e8; color: var(--bad); }
    .pill.warn { background: #fff1d7; color: var(--warn); }
    .muted {
      color: var(--muted);
      font-size: 13px;
    }
    .empty {
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 18px;
      text-align: center;
      background: #fbfcfd;
    }
    @media (max-width: 920px) {
      header { padding: 20px; }
      main { grid-template-columns: 1fr; padding: 12px; }
      aside { position: static; }
      .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <header>
    <h1>OpenRepo Support Agent</h1>
    <p class="subhead">Local demo for a repo-aware support agent runtime: intent routing, multi-agent trace, MCP-style tool calls, citations, monitor events, memory, and approval-aware patch planning.</p>
  </header>
  <main>
    <aside>
      <label for="question">Question</label>
      <textarea id="question">Where is the command line entrypoint implemented?</textarea>
      <div class="row">
        <input id="session" value="web-demo" aria-label="Session id">
        <button id="run">Run</button>
      </div>
      <p class="muted">Sample prompts</p>
      <div id="examples"></div>
    </aside>
    <div class="workspace">
      <section class="panel">
        <h2>Run Summary</h2>
        <div class="summary-grid">
          <div class="stat"><span>Run</span><strong id="run-id">-</strong></div>
          <div class="stat"><span>Intent</span><strong id="intent">-</strong></div>
          <div class="stat"><span>Tools</span><strong id="tool-count">-</strong></div>
          <div class="stat"><span>Monitor</span><strong id="monitor">-</strong></div>
        </div>
      </section>
      <section class="panel">
        <h2>Answer</h2>
        <div id="answer" class="empty">Run a question to inspect the agent output.</div>
      </section>
      <section class="panel">
        <h2>Multi-Agent Trace</h2>
        <div id="trace" class="list"></div>
      </section>
      <section class="panel">
        <h2>Tool Calls</h2>
        <div id="tools" class="list"></div>
      </section>
      <section class="panel">
        <h2>Citations</h2>
        <div id="citations" class="list"></div>
      </section>
      <section class="panel">
        <h2>Event Log</h2>
        <pre id="events">[]</pre>
      </section>
    </div>
  </main>
  <script>
    const question = document.querySelector("#question");
    const session = document.querySelector("#session");
    const run = document.querySelector("#run");
    const examples = document.querySelector("#examples");

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function renderList(node, items, renderer, emptyText) {
      if (!items || items.length === 0) {
        node.innerHTML = `<div class="empty">${escapeHtml(emptyText)}</div>`;
        return;
      }
      node.innerHTML = items.map(renderer).join("");
    }

    async function loadExamples() {
      const response = await fetch("/api/examples");
      const payload = await response.json();
      examples.innerHTML = payload.questions.map((item) => {
        return `<button class="secondary" type="button">${escapeHtml(item)}</button>`;
      }).join("");
      examples.querySelectorAll("button").forEach((button) => {
        button.addEventListener("click", () => {
          question.value = button.textContent;
        });
      });
    }

    async function ask() {
      run.disabled = true;
      run.textContent = "Running";
      try {
        const response = await fetch("/api/ask", {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify({
            question: question.value,
            session_id: session.value
          })
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || "Request failed");
        }
        render(payload);
      } catch (error) {
        document.querySelector("#answer").innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
      } finally {
        run.disabled = false;
        run.textContent = "Run";
      }
    }

    function render(payload) {
      document.querySelector("#run-id").textContent = payload.run_id;
      document.querySelector("#intent").textContent = payload.intent;
      document.querySelector("#tool-count").textContent = payload.tool_results.length;
      document.querySelector("#monitor").textContent = payload.monitor.status || "-";
      document.querySelector("#answer").innerHTML = `<pre class="answer">${escapeHtml(payload.answer)}</pre>`;
      document.querySelector("#events").textContent = JSON.stringify(payload.events, null, 2);

      renderList(document.querySelector("#trace"), payload.role_trace, (item) => `
        <div class="item">
          <div class="item-title"><span>${escapeHtml(item.role)}</span><span class="pill">agent</span></div>
          <div>${escapeHtml(item.decision)}</div>
          <pre>${escapeHtml(JSON.stringify(item.metadata, null, 2))}</pre>
        </div>
      `, "No role trace for this workflow.");

      renderList(document.querySelector("#tools"), payload.tool_results, (item) => `
        <div class="item">
          <div class="item-title">
            <span>${escapeHtml(item.name)}</span>
            <span class="pill ${item.ok ? "ok" : "bad"}">${item.ok ? "ok" : "error"}</span>
          </div>
          <pre>${escapeHtml(item.content)}</pre>
        </div>
      `, "No tool calls yet.");

      renderList(document.querySelector("#citations"), payload.citations, (item) => `
        <div class="item">
          <div class="item-title"><span>${escapeHtml(item.path)}:${item.line_start}-${item.line_end}</span><span class="pill ok">citation</span></div>
          <pre>${escapeHtml(item.snippet)}</pre>
        </div>
      `, "No citations returned.");
    }

    run.addEventListener("click", ask);
    loadExamples();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
