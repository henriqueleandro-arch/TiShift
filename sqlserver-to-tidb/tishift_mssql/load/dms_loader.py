"""DMS loading strategy (placeholder orchestration)."""

from __future__ import annotations

from tishift_mssql.load.models import LoadPlan, LoadResult


def run_dms_load(plan: LoadPlan, dms_instance_class: str) -> LoadResult:
    """Execute AWS DMS full load orchestration placeholder."""
    loaded = [t for t in plan.tables if t not in set(plan.excluded_tables)]
    return LoadResult(
        strategy="dms",
        total_tables=len(plan.tables),
        loaded_tables=loaded,
        skipped_tables=[t for t in plan.tables if t not in loaded],
        notes=[
            f"DMS strategy selected with instance class {dms_instance_class}",
            "Actual DMS task creation is planned for next iteration",
        ],
    )
