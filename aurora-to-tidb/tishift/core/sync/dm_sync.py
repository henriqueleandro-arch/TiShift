"""TiDB DM configuration generator stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DMSyncPlan:
    notes: str


def build_dm_plan() -> DMSyncPlan:
    return DMSyncPlan(notes="Generate TiDB DM source/worker/task configuration")
