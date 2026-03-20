"""Metrics stubs for Phase 1 scanner."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MetricsCollector:
    enabled: bool = False
    port: int = 9090

    def start(self) -> None:
        """Start metrics endpoint in later phases."""
        return

    def record_scan(self, success: bool) -> None:
        """Record scan outcome in later phases."""
        _ = success
        return
