"""CLI command: tishift scan.

Connects to Aurora MySQL, runs the full scan pipeline, and outputs
results in the requested formats.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import click
from rich.console import Console

from tishift.cli.formatters import format_scan_report
from tishift.config import TiShiftConfig, load_config
from tishift.connection import get_source_connection
from tishift.core.scan.reporters.html_report import generate_html_report
from tishift.core.scan.reporters.json_report import to_json_string
from tishift.core.scan.reporters.markdown_report import generate_markdown_report
from tishift.core.scan.reporters.pdf_report import generate_executive_pdf
from tishift.core.scan.scanner import run_scan
from tishift.models import TargetDeployment
from tishift.run_logger import RunLogger, anonymize_host, fingerprint, summarize_report

console = Console()


@click.command("scan")
@click.option(
    "--config", "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=Path("tishift.yaml"),
    help="Path to config file.",
)
@click.option("--database", default=None, help="Specific database to scan (default: all).")
@click.option(
    "--target",
    type=click.Choice(["cloud", "self-hosted"]),
    default="cloud",
    help="Target deployment: cloud (TiDB Cloud, default) or self-hosted.",
)
@click.option(
    "--format", "output_formats",
    default="cli",
    help="Output formats: cli, json, html, pdf, markdown (comma-separated).",
)
@click.option(
    "--output-dir", "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory for report files.",
)
@click.option("--quiet", is_flag=True, help="Suppress CLI output.")
@click.option("--include-query-log", is_flag=True, help="Analyze performance_schema query digests.")
@click.option("--ai", "include_ai", is_flag=True, help="Enable AI-powered stored procedure analysis.")
@click.option("--no-cost-analysis", is_flag=True, help="Disable automatic cost analysis.")
@click.option("--sample-rows", default=0, type=int, help="Sample rows per table for edge cases.")
def scan_command(
    config_path: Path,
    database: str | None,
    target: str,
    output_formats: str,
    output_dir: Path | None,
    quiet: bool,
    include_query_log: bool,
    include_ai: bool,
    no_cost_analysis: bool,
    sample_rows: int,
) -> None:
    """Scan Aurora MySQL and produce a migration readiness report."""
    cfg = load_config(config_path)
    formats = [f.strip().lower() for f in output_formats.split(",")]
    target_enum = TargetDeployment(target)

    if output_dir is None:
        output_dir = Path(cfg.output.dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    db = database or cfg.source.database

    # Auto-enable cost analysis when AWS identifiers are configured.
    include_cost_analysis = not no_cost_analysis and bool(
        cfg.aws.db_instance_identifier or cfg.aws.db_cluster_identifier
    )

    logger = RunLogger(phase="scan")
    logger.started(metrics={
        "source_type": anonymize_host(cfg.source.host),
        "database_fingerprint": fingerprint(db or "*"),
        "target": target,
    })
    t0 = time.monotonic()

    if not quiet:
        console.print(f"[bold]Connecting to {cfg.source.host}:{cfg.source.port}...[/bold]")

    try:
        with get_source_connection(cfg.source) as conn:
            report = run_scan(
                conn,
                source_host=cfg.source.host,
                database=db if db != "*" else None,
                include_query_log=include_query_log,
                include_ai=include_ai,
                include_cost_analysis=include_cost_analysis,
                sample_rows=sample_rows,
                ai_config=cfg.ai,
                aws_config=cfg.aws,
                target=target_enum,
            )
    except Exception as exc:
        logger.failed(exc, duration_ms=int((time.monotonic() - t0) * 1000))
        raise

    summary = summarize_report(report)
    logger.completed(metrics=summary, duration_ms=int((time.monotonic() - t0) * 1000))

    # ---- Output ----
    if "cli" in formats and not quiet:
        format_scan_report(report, console)

    if "json" in formats:
        json_path = output_dir / "tishift-report.json"
        json_path.write_text(to_json_string(report))
        if not quiet:
            console.print(f"  JSON report: {json_path}")

    if "html" in formats:
        html_path = output_dir / "tishift-report.html"
        html_path.write_text(generate_html_report(report))
        if not quiet:
            console.print(f"  HTML report: {html_path}")

    if "markdown" in formats:
        md_path = output_dir / "tishift-report.md"
        md_path.write_text(generate_markdown_report(report))
        if not quiet:
            console.print(f"  Markdown report: {md_path}")

    if "pdf" in formats:
        pdf_path = output_dir / "tishift-report-executive.pdf"
        pdf_path.write_bytes(generate_executive_pdf(report))
        if not quiet:
            console.print(f"  PDF report: {pdf_path}")

    if not quiet:
        console.print(f"\n[bold green]Scan complete.[/bold green] Score: {report.scoring.overall_score}/100")
