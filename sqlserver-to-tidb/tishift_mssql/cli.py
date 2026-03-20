"""CLI entrypoint for tishift-mssql."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from tishift_mssql.check.command import run_check
from tishift_mssql.config import load_config
from tishift_mssql.convert.command import run_convert
from tishift_mssql.load.command import run_load
from tishift_mssql.scan.command import run_scan
from tishift_mssql.scan.reporters.cli_report import render_cli_report
from tishift_mssql.scan.reporters.html_report import generate_html_report
from tishift_mssql.scan.reporters.json_report import generate_json_report
from tishift_mssql.sync.command import run_sync


@click.group(help="TiShift SQL Server migration toolkit")
def main() -> None:
    """Main CLI group."""


@main.command("scan")
@click.option("--config", "config_path", default="tishift-mssql.yaml", type=click.Path(path_type=Path), show_default=True)
@click.option("--database", default=None, help="Specific database to scan")
@click.option("--format", "output_formats", multiple=True, type=click.Choice(["cli", "json", "html"], case_sensitive=False), default=("cli",))
@click.option("--output-dir", type=click.Path(path_type=Path), default=None)
@click.option("--include-query-log", is_flag=True, default=False)
@click.option("--cost-analysis", is_flag=True, default=False)
@click.option("--ai", is_flag=True, default=False, help="Reserved for later phases")
@click.option("--quiet", is_flag=True, default=False)
@click.option("--verbose", is_flag=True, default=False)
def scan_command(
    config_path: Path,
    database: str | None,
    output_formats: tuple[str, ...],
    output_dir: Path | None,
    include_query_log: bool,
    cost_analysis: bool,
    ai: bool,
    quiet: bool,
    verbose: bool,
) -> None:
    """Run SQL Server migration readiness scan."""
    _ = (ai, verbose)
    config = load_config(config_path)
    out_dir = output_dir or Path(config.output.dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    console = None if quiet else Console()
    report = run_scan(
        config,
        database=database,
        include_query_log=include_query_log,
        include_cost=cost_analysis,
        console=console,
    )

    normalized_formats = {fmt.lower() for fmt in output_formats}

    if "cli" in normalized_formats and console:
        render_cli_report(report, console)

    if "json" in normalized_formats:
        json_path = out_dir / "tishift-mssql-report.json"
        generate_json_report(report, json_path)
        if console:
            console.print(f"JSON: {json_path}")

    if "html" in normalized_formats:
        html_path = out_dir / "tishift-mssql-report.html"
        html_path.write_text(generate_html_report(report))
        if console:
            console.print(f"HTML: {html_path}")


@main.command("convert")
@click.option("--config", "config_path", default=None, type=click.Path(path_type=Path), help="Config path (required for --apply)")
@click.option("--scan-report", "scan_report_path", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--sp-only", is_flag=True, default=False)
@click.option("--schema-only", is_flag=True, default=False)
@click.option("--ai", is_flag=True, default=False)
@click.option(
    "--language",
    type=click.Choice(["python", "go", "java", "javascript"], case_sensitive=False),
    default="python",
    show_default=True,
)
@click.option("--apply", "apply_changes", is_flag=True, default=False)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("./tishift-convert"), show_default=True)
@click.option(
    "--schema-mapping",
    type=click.Choice(["flatten", "prefix", "database"], case_sensitive=False),
    default="flatten",
    show_default=True,
)
@click.option("--quiet", is_flag=True, default=False)
def convert_command(
    config_path: Path | None,
    scan_report_path: Path,
    sp_only: bool,
    schema_only: bool,
    ai: bool,
    language: str,
    apply_changes: bool,
    dry_run: bool,
    output_dir: Path,
    schema_mapping: str,
    quiet: bool,
) -> None:
    """Convert scan output into TiDB-compatible schema and app-code stubs."""
    if apply_changes and config_path is None:
        raise click.UsageError("--apply requires --config")

    config = load_config(config_path) if config_path else None
    console = None if quiet else Console()

    result = run_convert(
        config=config,
        scan_report_path=scan_report_path,
        output_dir=output_dir,
        sp_only=sp_only,
        schema_only=schema_only,
        ai_enabled=ai,
        language=language.lower(),
        apply=apply_changes,
        dry_run=dry_run,
        schema_mapping=schema_mapping.lower(),
        console=console,
    )

    if console:
        console.print(f"Schema statements: {len(result.schema_statements)}")
        console.print(f"Procedure artifacts: {len(result.procedure_artifacts)}")
        if result.schema_warnings:
            console.print(f"Warnings: {len(result.schema_warnings)}")
        console.print(f"Output: {output_dir}")


@main.command("load")
@click.option("--config", "config_path", default="tishift-mssql.yaml", type=click.Path(path_type=Path), show_default=True)
@click.option("--strategy", type=click.Choice(["auto", "direct", "dms", "lightning"], case_sensitive=False), default="auto", show_default=True)
@click.option("--concurrency", default=4, show_default=True, type=int)
@click.option("--tables", default="*", show_default=True)
@click.option("--exclude-tables", default="", show_default=False)
@click.option("--s3-bucket", default=None)
@click.option("--dms-instance-class", default="dms.r5.large", show_default=True)
@click.option("--resume", is_flag=True, default=False)
@click.option("--continuation-token", default=None)
@click.option("--schema-first/--no-schema-first", default=True, show_default=True)
@click.option("--drop-indexes/--no-drop-indexes", default=True, show_default=True)
@click.option(
    "--schema-mapping",
    type=click.Choice(["flatten", "prefix", "database"], case_sensitive=False),
    default="flatten",
    show_default=True,
)
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("./tishift-load"), show_default=True)
@click.option("--quiet", is_flag=True, default=False)
def load_command(
    config_path: Path,
    strategy: str,
    concurrency: int,
    tables: str,
    exclude_tables: str,
    s3_bucket: str | None,
    dms_instance_class: str,
    resume: bool,
    continuation_token: str | None,
    schema_first: bool,
    drop_indexes: bool,
    schema_mapping: str,
    output_dir: Path,
    quiet: bool,
) -> None:
    """Bulk-load source data into TiDB using selected strategy."""
    config = load_config(config_path)
    console = None if quiet else Console()
    run_load(
        config=config,
        strategy=strategy.lower(),
        concurrency=concurrency,
        tables=tables,
        exclude_tables=exclude_tables,
        s3_bucket=s3_bucket,
        dms_instance_class=dms_instance_class,
        resume=resume,
        continuation_token=continuation_token,
        schema_first=schema_first,
        drop_indexes=drop_indexes,
        schema_mapping=schema_mapping.lower(),
        output_dir=output_dir,
        console=console,
    )


@main.command("sync")
@click.option("--config", "config_path", default="tishift-mssql.yaml", type=click.Path(path_type=Path), show_default=True)
@click.option("--strategy", type=click.Choice(["dms", "dm"], case_sensitive=False), default="dms", show_default=True)
@click.option("--start-lsn", default=None)
@click.option("--dms-task-arn", default=None)
@click.option("--status", "status_only", is_flag=True, default=False)
@click.option("--stop", is_flag=True, default=False)
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("./tishift-sync"), show_default=True)
@click.option("--quiet", is_flag=True, default=False)
def sync_command(
    config_path: Path,
    strategy: str,
    start_lsn: str | None,
    dms_task_arn: str | None,
    status_only: bool,
    stop: bool,
    output_dir: Path,
    quiet: bool,
) -> None:
    """Start/stop/check CDC sync status."""
    config = load_config(config_path)
    console = None if quiet else Console()
    run_sync(
        config=config,
        strategy=strategy.lower(),
        start_lsn=start_lsn,
        dms_task_arn=dms_task_arn,
        status_only=status_only,
        stop=stop,
        output_dir=output_dir,
        console=console,
    )


@main.command("check")
@click.option("--config", "config_path", default="tishift-mssql.yaml", type=click.Path(path_type=Path), show_default=True)
@click.option("--schema-only", is_flag=True, default=False)
@click.option("--tables", default="*", show_default=True)
@click.option("--exclude-tables", default="", show_default=False)
@click.option("--concurrency", default=16, show_default=True, type=int)
@click.option("--row-batch-size", default=20000, show_default=True, type=int)
@click.option("--sample-rate", default=1.0, show_default=True, type=float)
@click.option("--continuous", is_flag=True, default=False)
@click.option("--interval", default=300, show_default=True, type=int)
@click.option("--fail-on-mismatch", is_flag=True, default=False)
@click.option(
    "--schema-mapping",
    type=click.Choice(["flatten", "prefix", "database"], case_sensitive=False),
    default="flatten",
    show_default=True,
)
@click.option("--output", "output_formats", default="cli,json", show_default=True)
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("./tishift-check"), show_default=True)
@click.option("--quiet", is_flag=True, default=False)
def check_command(
    config_path: Path,
    schema_only: bool,
    tables: str,
    exclude_tables: str,
    concurrency: int,
    row_batch_size: int,
    sample_rate: float,
    continuous: bool,
    interval: int,
    fail_on_mismatch: bool,
    schema_mapping: str,
    output_formats: str,
    output_dir: Path,
    quiet: bool,
) -> None:
    """Validate source and target consistency."""
    config = load_config(config_path)
    console = None if quiet else Console()
    formats = tuple(fmt.strip().lower() for fmt in output_formats.split(",") if fmt.strip())
    result = run_check(
        config=config,
        schema_only=schema_only,
        tables=tables,
        exclude_tables=exclude_tables,
        concurrency=concurrency,
        row_batch_size=row_batch_size,
        sample_rate=sample_rate,
        continuous=continuous,
        interval=interval,
        fail_on_mismatch=fail_on_mismatch,
        schema_mapping=schema_mapping.lower(),
        output_formats=formats,
        output_dir=output_dir,
        console=console,
    )
    if fail_on_mismatch and not result.passed:
        raise click.ClickException("Data check detected mismatches")
