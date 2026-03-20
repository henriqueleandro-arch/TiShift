"""CLI command: tishift check."""

from __future__ import annotations

import time
from pathlib import Path

import click

from tishift.config import load_config
from tishift.connection import get_source_connection, get_target_connection
from tishift.core.check.table_checker import compare_row_counts, compare_table_structures
from tishift.run_logger import RunLogger, fingerprint


@click.command("check")
@click.option(
    "--config", "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=Path("tishift.yaml"),
    help="Path to config file.",
)
@click.option("--schema", default=None, help="Schema/database to check.")
def check_command(config_path: Path, schema: str | None) -> None:
    """Validate table structures and row counts between source and target."""
    cfg = load_config(config_path)
    target_schema = schema or cfg.source.database
    if target_schema in (None, "*"):
        raise click.ClickException("--schema is required when source database is '*'")

    logger = RunLogger(phase="check")
    logger.started(metrics={"schema_fingerprint": fingerprint(target_schema)})
    t0 = time.monotonic()

    try:
        with get_source_connection(cfg.source) as src, get_target_connection(cfg.target) as tgt:
            row_results = compare_row_counts(src, tgt, target_schema)
            col_results = compare_table_structures(src, tgt, target_schema)
    except Exception as exc:
        logger.failed(exc, duration_ms=int((time.monotonic() - t0) * 1000))
        raise

    mismatched_rows = [r for r in row_results if not r.row_count_match]
    mismatched_cols = [c for c in col_results if not c.match]

    logger.completed(
        metrics={
            "tables_checked": len(row_results),
            "row_count_mismatches": len(mismatched_rows),
            "column_type_mismatches": len(mismatched_cols),
        },
        duration_ms=int((time.monotonic() - t0) * 1000),
    )

    click.echo(f"Row count mismatches: {len(mismatched_rows)}")
    click.echo(f"Column type mismatches: {len(mismatched_cols)}")
