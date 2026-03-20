"""Continuation token support for resumable load."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4


STATE_DIR = ".tishift-state"


def state_dir(base: Path) -> Path:
    path = base / STATE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def issue_token() -> str:
    return uuid4().hex


def write_state(base: Path, token: str, payload: dict[str, object]) -> Path:
    path = state_dir(base) / f"load-{token}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def read_state(base: Path, token: str) -> dict[str, object]:
    path = state_dir(base) / f"load-{token}.json"
    if not path.exists():
        raise FileNotFoundError(f"Continuation token not found: {token}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("Invalid continuation payload")
    return payload
