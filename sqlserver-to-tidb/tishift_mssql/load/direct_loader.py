"""Direct loading strategy (placeholder orchestration)."""

from __future__ import annotations

from tishift_mssql.load.models import LoadPlan, LoadResult


def run_direct_load(plan: LoadPlan) -> LoadResult:
    """Execute direct CSV/LOAD DATA style load plan."""
    loaded = [t for t in plan.tables if t not in set(plan.excluded_tables)]
    return LoadResult(
        strategy="direct",
        total_tables=len(plan.tables),
        loaded_tables=loaded,
        skipped_tables=[t for t in plan.tables if t not in loaded],
        notes=["Direct strategy selected (BCP export -> LOAD DATA pipeline placeholder)"],
    )
