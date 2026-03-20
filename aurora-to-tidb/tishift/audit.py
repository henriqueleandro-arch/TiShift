"""Audit log writer for tool invocations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class AuditEvent:
    tool: str
    params: dict[str, Any]
    outcome: str
    timestamp: str


class AuditLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, tool: str, params: dict[str, Any], outcome: str) -> None:
        event = AuditEvent(
            tool=tool,
            params=params,
            outcome=outcome,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event)) + "\n")
