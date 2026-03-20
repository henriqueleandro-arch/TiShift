"""Scan orchestrator.

Calls all collectors and analyzers in sequence and assembles the final
ScanReport.  This is the public API that the CLI calls.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pymysql

from tishift.core.scan.analyzers.ai_analyzer import analyze_stored_procedures
from tishift.core.scan.analyzers.automation import compute_automation
from tishift.core.scan.analyzers.compatibility import assess_compatibility
from tishift.core.scan.analyzers.cost import analyze_costs
from tishift.core.scan.analyzers.scoring import compute_scores
from tishift.core.scan.collectors.aurora import collect_aurora_metadata
from tishift.core.scan.collectors.cloudwatch import collect_cloudwatch_metrics
from tishift.core.scan.collectors.data_profile import collect_data_profile
from tishift.core.scan.collectors.queries import collect_query_patterns
from tishift.core.scan.collectors.schema import collect_schema
from tishift.config import AIConfig, AWSConfig
from tishift.models import Issue, ScanReport, TargetDeployment

logger = logging.getLogger(__name__)


def run_scan(
    conn: pymysql.Connection,
    *,
    source_host: str = "",
    database: str | None = None,
    include_query_log: bool = False,
    include_ai: bool = False,
    include_cost_analysis: bool = False,
    sample_rows: int = 0,
    ai_config: AIConfig | None = None,
    aws_config: AWSConfig | None = None,
    target: TargetDeployment = TargetDeployment.CLOUD,
) -> ScanReport:
    """Run the full scan pipeline and return a ScanReport.

    Parameters
    ----------
    conn:
        An open PyMySQL connection to the source database (must be
        read-only).
    source_host:
        The hostname of the source, for display in the report.
    database:
        Specific database to scan, or None / ``"*"`` for all.
    include_query_log:
        If True, also scan performance_schema for query patterns.
    include_ai:
        If True, run AI analysis on stored procedures/functions.
    include_cost_analysis:
        If True, collect CloudWatch metrics and compute cost comparison.
    sample_rows:
        Reserved for future data sampling (no-op in Phase 3).
    """
    report = ScanReport(
        generated_at=datetime.now(timezone.utc),
        target=target.value,
        source_host=source_host,
        database=database or "*",
    )

    # ---- Collectors ----
    logger.info("Collecting schema inventory...")
    report.schema_inventory = collect_schema(conn, database=database)

    logger.info("Collecting data profile...")
    report.data_profile = collect_data_profile(conn, database=database)

    logger.info("Collecting Aurora metadata...")
    report.aurora_metadata = collect_aurora_metadata(conn)

    if include_query_log:
        logger.info("Collecting query patterns from performance_schema...")
        report.query_patterns = collect_query_patterns(conn)

    if include_ai:
        logger.info("Running AI analysis on stored procedures...")
        if ai_config is None:
            ai_config = AIConfig()
        report.sp_analysis = analyze_stored_procedures(
            report.schema_inventory.routines,
            ai_config,
        )

    if include_cost_analysis:
        logger.info("Collecting CloudWatch metrics for cost analysis...")
        if aws_config is None:
            aws_config = AWSConfig()
        metrics = collect_cloudwatch_metrics(aws=aws_config, source_host=source_host)
        if metrics is not None:
            report.cost_analysis = analyze_costs(
                metrics=metrics,
                profile=report.data_profile,
                metadata=report.aurora_metadata,
            )

    # ---- Analyzers ----
    logger.info("Assessing TiDB compatibility...")
    report.assessment = assess_compatibility(report.schema_inventory)

    if report.sp_analysis:
        from dataclasses import replace
        ai_index = {
            f"{a.routine_schema}.{a.routine_name}": a for a in report.sp_analysis
        }
        enriched: list[Issue] = []
        for issue in report.assessment.warnings:
            if issue.type in ("stored_procedure", "user_defined_function"):
                analysis = ai_index.get(issue.object_name)
                if analysis:
                    issue = replace(
                        issue,
                        difficulty=analysis.difficulty,
                        automation_pct=analysis.automation_pct,
                        ai_suggestion=analysis.suggested_approach,
                        summary=analysis.summary,
                    )
            enriched.append(issue)
        report.assessment.warnings = enriched

    logger.info("Computing readiness scores...")
    report.scoring = compute_scores(
        inventory=report.schema_inventory,
        profile=report.data_profile,
        metadata=report.aurora_metadata,
        query_patterns=report.query_patterns,
        ai_analysis=report.sp_analysis if report.sp_analysis else None,
        target=target,
    )

    logger.info("Computing automation coverage...")
    report.automation = compute_automation(
        report.schema_inventory,
        ai_analysis=report.sp_analysis if report.sp_analysis else None,
    )

    logger.info(
        "Scan complete: score=%d/100 (%s), %d tables, %.1f GB",
        report.scoring.overall_score,
        report.scoring.rating.value,
        len(report.schema_inventory.tables),
        report.data_profile.total_data_mb / 1024,
    )
    return report
