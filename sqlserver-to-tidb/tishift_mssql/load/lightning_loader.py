"""Lightning loading strategy (placeholder orchestration)."""

from __future__ import annotations

from tishift_mssql.load.models import LoadPlan, LoadResult


def run_lightning_load(plan: LoadPlan, s3_bucket: str | None) -> LoadResult:
    """Execute TiDB Lightning import orchestration placeholder."""
    loaded = [t for t in plan.tables if t not in set(plan.excluded_tables)]
    notes = ["Lightning strategy selected (BCP export -> S3 -> Lightning placeholder)"]
    if s3_bucket:
        notes.append(f"S3 bucket: {s3_bucket}")
    return LoadResult(
        strategy="lightning",
        total_tables=len(plan.tables),
        loaded_tables=loaded,
        skipped_tables=[t for t in plan.tables if t not in loaded],
        notes=notes,
    )
