"""Data models for sync command."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SyncStatus:
    strategy: str
    running: bool
    lag_seconds: int
    checkpoint: str | None = None
    notes: list[str] = field(default_factory=list)
