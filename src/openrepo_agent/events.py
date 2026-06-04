from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Event:
    type: str
    payload: dict[str, Any]
    timestamp: str = field(default_factory=utc_now)


class EventLog:
    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id or uuid4().hex[:12]
        self.events: list[Event] = []

    def record(self, event_type: str, **payload: Any) -> None:
        self.events.append(Event(type=event_type, payload=payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "events": [asdict(event) for event in self.events],
        }

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        output = directory / f"{self.run_id}.json"
        output.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output
