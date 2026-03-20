"""CLI command: tishift convert."""

from __future__ import annotations

import json
import time
from pathlib import Path

import click

from tishift.config import load_config
from tishift.run_logger import RunLogger
from tishift.connection import get_target_connection
from tishift.core.convert.apply import apply_schema
from tishift.core.convert.diff_generator import generate_schema_diff
from tishift.core.convert.event_converter import convert_events
from tishift.core.convert.schema_transformer import TransformOptions, transform_schema
from tishift.core.convert.sp_converter import convert_stored_procedures
from tishift.core.convert.trigger_converter import convert_triggers
from tishift.models import SchemaInventory


@click.command("convert")
@click.option(
    "--config", "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=Path("tishift.yaml"),
    help="Path to config file.",
)
@click.option(
    "--scan-report",
    "scan_report_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to JSON report from tishift scan.",
)
@click.option(
    "--target",
    type=click.Choice(["cloud", "self-hosted"]),
    default="cloud",
    help="Target deployment: cloud (TiDB Cloud, default) or self-hosted.",
)
@click.option("--sp-only", is_flag=True, help="Only convert stored procedures.")
@click.option("--schema-only", is_flag=True, help="Only convert schema DDL.")
@click.option("--ai", "use_ai", is_flag=True, help="Use AI for stored procedure conversion.")
@click.option("--language", default="python", help="Target language for SP conversion.")
@click.option("--apply", "apply_schema_flag", is_flag=True, help="Apply schema to target TiDB.")
@click.option("--dry-run", is_flag=True, help="Generate diff without applying.")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("./tishift-convert"),
    help="Where to write output files.",
)
def convert_command(
    config_path: Path,
    scan_report_path: Path,
    target: str,
    sp_only: bool,
    schema_only: bool,
    use_ai: bool,
    language: str,
    apply_schema_flag: bool,
    dry_run: bool,
    output_dir: Path,
) -> None:
    """Convert schema and stored procedures to TiDB-compatible artifacts."""
    cfg = load_config(config_path)
    data = json.loads(scan_report_path.read_text())

    inventory = _inventory_from_report(data)

    logger = RunLogger(phase="convert")
    logger.started(metrics={
        "table_count": len(inventory.tables),
        "routine_count": len(inventory.routines),
        "trigger_count": len(inventory.triggers),
        "event_count": len(inventory.events),
        "sp_only": sp_only,
        "schema_only": schema_only,
    })
    t0 = time.monotonic()

    output_dir.mkdir(parents=True, exist_ok=True)
    schema_dir = output_dir / "schema"
    proc_dir = output_dir / "procedures"
    trigger_dir = output_dir / "triggers"
    event_dir = output_dir / "events"
    diff_dir = output_dir / "diff"

    for d in (schema_dir, proc_dir, trigger_dir, event_dir, diff_dir):
        d.mkdir(parents=True, exist_ok=True)

    conversion_notes_count = 0
    tables_converted = 0
    sp_converted = 0
    triggers_converted = 0
    events_converted = 0
    errors: list[str] = []

    try:
        if not sp_only:
            options = TransformOptions(target_is_cloud=(target == "cloud"))
            result = transform_schema(inventory, options)

            (schema_dir / "01-create-tables.sql").write_text(result.create_tables_sql)
            (schema_dir / "02-create-indexes.sql").write_text(result.create_indexes_sql)
            (schema_dir / "03-create-views.sql").write_text(result.create_views_sql)
            (schema_dir / "04-foreign-keys.sql").write_text(result.foreign_keys_sql)
            (schema_dir / "conversion-notes.md").write_text("\n".join(result.conversion_notes))

            conversion_notes_count = len(result.conversion_notes)
            tables_converted = len(inventory.tables)

            diff = generate_schema_diff(result.original_schema_sql, result.create_tables_sql)
            (diff_dir / "schema-diff.sql").write_text(diff.unified_diff)
            (diff_dir / "schema-diff.html").write_text(diff.html_diff)

            if apply_schema_flag and not dry_run:
                with get_target_connection(cfg.target) as conn:
                    apply_schema(
                        conn,
                        [
                            schema_dir / "01-create-tables.sql",
                            schema_dir / "02-create-indexes.sql",
                            schema_dir / "03-create-views.sql",
                            schema_dir / "04-foreign-keys.sql",
                        ],
                    )

        if not schema_only:
            sp_results, _ = convert_stored_procedures(
                inventory.routines,
                language=language,
                use_ai=use_ai,
                ai_config=cfg.ai,
            )
            sp_converted = len(sp_results)
            for sp in sp_results:
                (proc_dir / sp.filename).write_text(sp.code)

            trigger_results = convert_triggers(inventory.triggers)
            triggers_converted = len(trigger_results)
            for trg in trigger_results:
                (trigger_dir / trg.filename).write_text(trg.code)
            (trigger_dir / "README.md").write_text("Integrate trigger middleware into application layer.")

            event_results = convert_events(inventory.events)
            events_converted = len(event_results)
            for evt in event_results:
                (event_dir / evt.filename).write_text(evt.code)
            (event_dir / "README.md").write_text("Schedule these with cron or a managed scheduler.")

        (output_dir / "apply.sh").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "# Set TIDB_HOST, TIDB_PORT, TIDB_USER, TIDB_PASSWORD as environment variables.\n"
            "# MYSQL_PWD avoids exposing the password in process listings.\n"
            "export MYSQL_PWD=\"$TIDB_PASSWORD\"\n"
            'mysql -h "$TIDB_HOST" -P "$TIDB_PORT" -u "$TIDB_USER" < schema/01-create-tables.sql\n'
            'mysql -h "$TIDB_HOST" -P "$TIDB_PORT" -u "$TIDB_USER" < schema/02-create-indexes.sql\n'
            'mysql -h "$TIDB_HOST" -P "$TIDB_PORT" -u "$TIDB_USER" < schema/03-create-views.sql\n'
            'mysql -h "$TIDB_HOST" -P "$TIDB_PORT" -u "$TIDB_USER" < schema/04-foreign-keys.sql\n'
            "unset MYSQL_PWD\n"
        )
    except Exception as exc:
        logger.failed(exc, duration_ms=int((time.monotonic() - t0) * 1000))
        raise

    logger.completed(
        metrics={
            "tables_converted": tables_converted,
            "conversion_notes_count": conversion_notes_count,
            "sp_converted": sp_converted,
            "triggers_converted": triggers_converted,
            "events_converted": events_converted,
        },
        duration_ms=int((time.monotonic() - t0) * 1000),
    )


def _inventory_from_report(data: dict) -> SchemaInventory:
    schema = data.get("schema_inventory") or {}
    return SchemaInventory(
        tables=[_obj_to_dataclass(TableInfo, o) for o in schema.get("tables", [])],
        columns=[_obj_to_dataclass(ColumnInfo, o) for o in schema.get("columns", [])],
        indexes=[_obj_to_dataclass(IndexInfo, o) for o in schema.get("indexes", [])],
        foreign_keys=[_obj_to_dataclass(ForeignKeyInfo, o) for o in schema.get("foreign_keys", [])],
        routines=[_obj_to_dataclass(RoutineInfo, o) for o in schema.get("routines", [])],
        triggers=[_obj_to_dataclass(TriggerInfo, o) for o in schema.get("triggers", [])],
        views=[_obj_to_dataclass(ViewInfo, o) for o in schema.get("views", [])],
        events=[_obj_to_dataclass(EventInfo, o) for o in schema.get("events", [])],
        partitions=[_obj_to_dataclass(PartitionInfo, o) for o in schema.get("partitions", [])],
        charset_usage=[_obj_to_dataclass(CharsetUsage, o) for o in schema.get("charset_usage", [])],
    )


def _obj_to_dataclass(cls, obj: dict):
    return cls(**obj)


from tishift.models import (
    CharsetUsage,
    ColumnInfo,
    EventInfo,
    ForeignKeyInfo,
    IndexInfo,
    PartitionInfo,
    RoutineInfo,
    TableInfo,
    TriggerInfo,
    ViewInfo,
)
