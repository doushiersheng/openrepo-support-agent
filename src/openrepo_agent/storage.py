from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .events import EventLog, utc_now
from .models import AgentResponse


class SQLiteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    repo_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    citations_json TEXT NOT NULL,
                    tool_results_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS memory_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    value TEXT NOT NULL,
                    source_run_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, kind, value),
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS approvals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    decided_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );
                """
            )

    def ensure_session(self, session_id: str, repo_path: str | Path) -> None:
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(session_id, repo_path, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    repo_path = excluded.repo_path,
                    updated_at = excluded.updated_at
                """,
                (session_id, str(Path(repo_path).resolve()), now, now),
            )

    def save_turn(self, session_id: str, response: AgentResponse, event_log: EventLog) -> None:
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO turns(
                    session_id, run_id, question, intent, answer, citations_json,
                    tool_results_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    response.run_id,
                    response.question,
                    response.intent,
                    response.answer,
                    json.dumps([asdict(citation) for citation in response.citations], ensure_ascii=False),
                    json.dumps([asdict(result) for result in response.tool_results], ensure_ascii=False),
                    now,
                ),
            )
            for event in event_log.events:
                connection.execute(
                    """
                    INSERT INTO events(session_id, run_id, event_type, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        response.run_id,
                        event.type,
                        json.dumps(event.payload, ensure_ascii=False, default=str),
                        event.timestamp,
                    ),
                )
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )

    def add_memory_items(self, session_id: str, run_id: str, items: list[tuple[str, str]]) -> None:
        now = utc_now()
        with self._connect() as connection:
            for kind, value in items:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO memory_items(session_id, kind, value, source_run_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (session_id, kind, value, run_id, now),
                )

    def load_memory_items(self, session_id: str, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT kind, value, source_run_id, created_at
                FROM memory_items
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def load_recent_turns(self, session_id: str, limit: int = 5) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, question, intent, answer, created_at
                FROM turns
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_approval(
        self,
        session_id: str,
        run_id: str,
        tool_name: str,
        args: dict[str, Any],
    ) -> int:
        now = utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO approvals(session_id, run_id, tool_name, args_json, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (
                    session_id,
                    run_id,
                    tool_name,
                    json.dumps(args, ensure_ascii=False, default=str),
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def list_approvals(
        self,
        session_id: str | None = None,
        status: str | None = "pending",
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id, session_id, run_id, tool_name, args_json, status, result_json,
                       created_at, decided_at
                FROM approvals
                {where}
                ORDER BY id DESC
                """,
                params,
            ).fetchall()
        approvals = []
        for row in rows:
            item = dict(row)
            item["args"] = json.loads(item.pop("args_json"))
            result_json = item.pop("result_json")
            item["result"] = json.loads(result_json) if result_json else None
            approvals.append(item)
        return approvals

    def get_approval(self, approval_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, session_id, run_id, tool_name, args_json, status, result_json,
                       created_at, decided_at
                FROM approvals
                WHERE id = ?
                """,
                (approval_id,),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["args"] = json.loads(item.pop("args_json"))
        result_json = item.pop("result_json")
        item["result"] = json.loads(result_json) if result_json else None
        return item

    def mark_approval_decided(
        self,
        approval_id: int,
        status: str,
        result: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE approvals
                SET status = ?, result_json = ?, decided_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    json.dumps(result, ensure_ascii=False, default=str),
                    utc_now(),
                    approval_id,
                ),
            )
