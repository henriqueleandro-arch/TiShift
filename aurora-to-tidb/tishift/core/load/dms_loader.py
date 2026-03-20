"""DMS load strategy stub (AWS DMS full load automation)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DMSLoadPlan:
    task_name: str
    notes: str


def build_dms_plan(task_name: str) -> DMSLoadPlan:
    return DMSLoadPlan(
        task_name=task_name,
        notes="Create replication instance, endpoints, and full load task in AWS DMS",
    )
