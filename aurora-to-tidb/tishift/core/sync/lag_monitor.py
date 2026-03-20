"""Replication lag monitoring stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LagStatus:
    lag_seconds: float
    status: str


def get_lag_status() -> LagStatus:
    return LagStatus(lag_seconds=0.0, status="unknown")
