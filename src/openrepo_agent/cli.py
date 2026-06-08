from __future__ import annotations

import argparse
from pathlib import Path

from .agent import OpenRepoSupportAgent
from .storage import SQLiteStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run OpenRepo Support Agent.")
    parser.add_argument("question", nargs="?", help="User question or support request.")
    parser.add_argument("--repo", default=".", help="Path to the local repository to inspect.")
    parser.add_argument(
        "--log-dir",
        default=".openrepo-agent/runs",
        help="Directory for JSON event logs.",
    )
    parser.add_argument(
        "--no-save-log",
        action="store_true",
        help="Print response without writing the event log.",
    )
    parser.add_argument(
        "--workflow",
        choices=["sequential", "multi_agent", "langgraph"],
        default="sequential",
        help="Workflow runtime to use.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use DEEPSEEK_API_KEY to enhance the final answer.",
    )
    parser.add_argument(
        "--session-id",
        help="Persist this turn under a conversation session id.",
    )
    parser.add_argument(
        "--db",
        default=".openrepo-agent/openrepo.sqlite",
        help="SQLite database path for sessions and memory.",
    )
    parser.add_argument(
        "--show-memory",
        action="store_true",
        help="Print session memory after the response.",
    )
    parser.add_argument(
        "--list-approvals",
        action="store_true",
        help="List pending approvals for the session/database.",
    )
    parser.add_argument(
        "--approve",
        type=int,
        help="Execute a pending approval by id.",
    )
    parser.add_argument(
        "--approval-status",
        default="pending",
        help="Approval status filter for --list-approvals. Use 'all' for every status.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    needs_store = bool(args.session_id or args.list_approvals or args.approve)
    store = SQLiteStore(args.db) if needs_store else None
    agent = OpenRepoSupportAgent(
        args.repo,
        workflow=args.workflow,
        use_llm=args.use_llm,
        session_id=args.session_id,
        store=store,
    )

    if args.list_approvals:
        status = None if args.approval_status == "all" else args.approval_status
        approvals = store.list_approvals(args.session_id, status=status) if store else []
        if not approvals:
            print("No approvals found.")
            return
        for approval in approvals:
            print(
                "#{id} [{status}] session={session_id} tool={tool_name} "
                "args={args}".format(**approval)
            )
        return

    if args.approve is not None:
        result = agent.approve(args.approve)
        status = "ok" if result.ok else "error"
        print(f"Approval #{args.approve}: {status}")
        print(result.content)
        return

    if not args.question:
        raise SystemExit("question is required unless --list-approvals or --approve is used")

    response = agent.answer(args.question)

    print(f"Run ID: {response.run_id}")
    print(f"Intent: {response.intent}")
    print()
    print(response.answer)

    if response.citations:
        print("\nCitations:")
        for citation in response.citations:
            print(f"- {citation.path}:{citation.line_start}-{citation.line_end}")

    print("\nTool calls:")
    for result in response.tool_results:
        status = "ok" if result.ok else "error"
        print(f"- {result.name}: {status}")

    if args.show_memory and store and args.session_id:
        print("\nSession memory:")
        memory_items = store.load_memory_items(args.session_id)
        if not memory_items:
            print("- No memory items yet")
        for item in memory_items:
            print(f"- {item['kind']}: {item['value']}")

    if not args.no_save_log:
        output = agent.event_log.save(Path(args.log_dir))
        print(f"\nSaved event log: {output}")


if __name__ == "__main__":
    main()
