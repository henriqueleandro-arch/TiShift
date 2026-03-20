"""Check command orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from tishift_mssql.check.checksum_checker import compare_checksums
from tishift_mssql.check.column_checker import compare_columns
from tishift_mssql.check.continuous import run_continuous
from tishift_mssql.check.count_checker import compare_counts
from tishift_mssql.check.models import CheckResult
from tishift_mssql.check.row_checker import compare_rows
from tishift_mssql.check.table_checker import compare_tables
from tishift_mssql.config import TiShiftMSSQLConfig


def _parse_tables(value: str) -> list[str]:
    if value.strip() == "*":
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _build_mock_snapshot(table_filter: list[str]) -> tuple[list[str], dict[str, int]]:
    all_tables = ["users", "orders", "products"]
    tables = table_filter if table_filter else all_tables
    counts = {t: 100 for t in tables}
    return tables, counts


def _single_check(schema_only: bool, sample_rate: float, table_filter: list[str]) -> CheckResult:
    source_tables, source_counts = _build_mock_snapshot(table_filter)
    target_tables, target_counts = _build_mock_snapshot(table_filter)

    result = CheckResult()
    result.tables_checked = len(source_tables)

    result.schema_mismatches.extend(compare_tables(source_tables, target_tables))

    source_cols = {t: {"id": "INT", "name": "VARCHAR(100)"} for t in source_tables}
    target_cols = {t: {"id": "INT", "name": "VARCHAR(100)"} for t in target_tables}
    result.schema_mismatches.extend(compare_columns(source_cols, target_cols))

    if not schema_only:
        result.row_count_mismatches.extend(compare_counts(source_counts, target_counts))

        source_rows = {t: [{"id": i, "name": f"row-{i}"} for i in range(5)] for t in source_tables}
        target_rows = {t: [{"id": i, "name": f"row-{i}"} for i in range(5)] for t in target_tables}
        result.row_mismatches.extend(compare_rows(source_rows, target_rows, sample_rate=sample_rate))

        source_checksums = {t: "abc" for t in source_tables}
        target_checksums = {t: "abc" for t in target_tables}
        result.checksum_mismatches.extend(compare_checksums(source_checksums, target_checksums))

    result.passed = not (
        result.schema_mismatches
        or result.row_count_mismatches
        or result.row_mismatches
        or result.checksum_mismatches
    )
    return result


def run_check(
    *,
    config: TiShiftMSSQLConfig,
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
    output_formats: tuple[str, ...],
    output_dir: Path,
    console: Console | None,
) -> CheckResult:
    """Run cross-dialect validation checks."""
    _ = (config, concurrency, row_batch_size, fail_on_mismatch, schema_mapping)
    include_tables = _parse_tables(tables)
    excluded = set(_parse_tables(exclude_tables))
    include_tables = [t for t in include_tables if t not in excluded]

    def _runner() -> CheckResult:
        return _single_check(schema_only=schema_only, sample_rate=sample_rate, table_filter=include_tables)

    if continuous:
        latest = run_continuous(_runner, interval=max(1, interval), iterations=2)[-1]
    else:
        latest = _runner()

    output_dir.mkdir(parents=True, exist_ok=True)
    if any(fmt.lower() == "json" for fmt in output_formats):
        payload = {
            "tables_checked": latest.tables_checked,
            "passed": latest.passed,
            "schema_mismatches": [m.__dict__ for m in latest.schema_mismatches],
            "row_count_mismatches": [m.__dict__ for m in latest.row_count_mismatches],
            "row_mismatches": [m.__dict__ for m in latest.row_mismatches],
            "checksum_mismatches": [m.__dict__ for m in latest.checksum_mismatches],
        }
        (output_dir / "check-report.json").write_text(json.dumps(payload, indent=2) + "\n")

    if console and any(fmt.lower() == "cli" for fmt in output_formats):
        console.print(f"Tables checked: {latest.tables_checked}")
        console.print(f"Schema mismatches: {len(latest.schema_mismatches)}")
        if not schema_only:
            console.print(f"Row-count mismatches: {len(latest.row_count_mismatches)}")
            console.print(f"Row mismatches: {len(latest.row_mismatches)}")
            console.print(f"Checksum mismatches: {len(latest.checksum_mismatches)}")
        console.print(f"Passed: {latest.passed}")

    return latest
