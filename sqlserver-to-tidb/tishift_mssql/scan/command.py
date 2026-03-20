"""Scan orchestration command."""

from __future__ import annotations

from datetime import datetime

from rich.console import Console

from tishift_mssql.config import TiShiftMSSQLConfig
from tishift_mssql.connection import get_source_connection
from tishift_mssql.models import ScanReport
from tishift_mssql.scan.analyzers.automation import compute_automation
from tishift_mssql.scan.analyzers.compatibility import assess_compatibility, evaluate_tier_fit
from tishift_mssql.scan.analyzers.scoring import compute_scores
from tishift_mssql.scan.collectors.cost import estimate_cost
from tishift_mssql.scan.collectors.data_profile import collect_data_profile
from tishift_mssql.scan.collectors.features import collect_features
from tishift_mssql.scan.collectors.queries import collect_query_patterns
from tishift_mssql.scan.collectors.schema import collect_schema
from tishift_mssql.scan.collectors.sqlserver_meta import collect_sqlserver_metadata
from tishift_mssql.progress import step_progress


def run_scan(
    config: TiShiftMSSQLConfig,
    *,
    database: str | None = None,
    include_query_log: bool = False,
    include_cost: bool = False,
    console: Console | None = None,
) -> ScanReport:
    """Run the SQL Server scanner and return a structured report."""
    tier = config.target.tier
    report = ScanReport(
        generated_at=datetime.utcnow(),
        source_host=config.source.host,
        database=database or config.source.database,
        target_tier=tier,
    )
    target_db = database or (config.source.database if config.source.database != "*" else None)

    with get_source_connection(config.source) as conn:
        with step_progress(console, "Collect schema inventory"):
            report.schema_inventory = collect_schema(conn, target_db)

        with step_progress(console, "Collect feature usage"):
            report.feature_scan = collect_features(report.schema_inventory)

        with step_progress(console, "Collect data profile"):
            report.data_profile = collect_data_profile(conn, target_db)

        with step_progress(console, "Collect SQL Server metadata"):
            report.sqlserver_metadata = collect_sqlserver_metadata(conn)
            report.sqlserver_metadata.auth_mode = config.source.auth

        if include_query_log:
            with step_progress(console, "Collect query patterns"):
                report.query_patterns = collect_query_patterns(conn)

    with step_progress(console, f"Assess compatibility (target: {tier})"):
        report.assessment = assess_compatibility(
            report.schema_inventory,
            report.feature_scan,
            report.sqlserver_metadata,
            profile=report.data_profile,
            tier=tier,
        )

    with step_progress(console, "Compute readiness scores"):
        report.scoring = compute_scores(
            inventory=report.schema_inventory,
            profile=report.data_profile,
            metadata=report.sqlserver_metadata,
            features=report.feature_scan,
            query_patterns=report.query_patterns,
            tier=tier,
        )

    with step_progress(console, "Evaluate tier fit"):
        report.tier_fit = evaluate_tier_fit(
            report.data_profile,
            report.sqlserver_metadata,
            report.schema_inventory,
        )

    with step_progress(console, "Compute automation coverage"):
        report.automation = compute_automation(
            report.schema_inventory,
            report.feature_scan,
            report.assessment,
        )

    if include_cost:
        with step_progress(console, "Estimate costs (SQL Server vs TiDB Cloud)"):
            report.cost_estimate = estimate_cost(
                report.sqlserver_metadata,
                tier=tier,
                total_data_mb=report.data_profile.total_data_mb,
            )

    return report
