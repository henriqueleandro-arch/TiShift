"""DMS sync (CDC) configuration stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DMSSyncPlan:
    notes: str


def build_dms_sync_plan() -> DMSSyncPlan:
    return DMSSyncPlan(notes="Configure DMS CDC task for ongoing replication")
