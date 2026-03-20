"""TiDB Lightning load strategy stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LightningPlan:
    notes: str


def build_lightning_plan() -> LightningPlan:
    return LightningPlan(
        notes="Export Aurora snapshot to S3 and load via TiDB Lightning",
    )
