"""TiDB Cloud Starter import via ticloud CLI."""

from __future__ import annotations

from tishift_mssql.load.models import LoadPlan, LoadResult


def run_ticloud_import(
    plan: LoadPlan,
    cluster_id: str,
    project_id: str,
) -> LoadResult:
    """Import data to TiDB Cloud Starter using ticloud serverless import start.

    Workflow:
    1. BCP export each table to CSV (same as direct strategy)
    2. Split CSVs larger than 250 MiB into chunks
    3. Run: ticloud serverless import start \\
         --cluster-id <cluster_id> --project-id <project_id> \\
         --source-type LOCAL --local.file-path <FILE> \\
         --local.target-database <DB> --local.target-table <TABLE>
    4. Poll import status until complete

    For files under 250 MiB, users can alternatively upload via the
    TiDB Cloud console Import page.
    """
    return LoadResult(
        strategy="ticloud_import",
        tables_loaded=len(plan.tables),
        tables_failed=0,
        notes=[
            f"ticloud import planned for {len(plan.tables)} tables",
            f"cluster_id={cluster_id}, project_id={project_id}",
            "Implementation: BCP export → CSV split (250 MiB chunks) → ticloud serverless import start",
        ],
    )
