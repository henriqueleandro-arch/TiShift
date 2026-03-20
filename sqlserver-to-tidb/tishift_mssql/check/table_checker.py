"""Table existence checker."""

from __future__ import annotations

from tishift_mssql.check.models import TableMismatch


def compare_tables(source_tables: list[str], target_tables: list[str]) -> list[TableMismatch]:
    """Compare table existence across source and target."""
    source_set = set(source_tables)
    target_set = set(target_tables)

    mismatches: list[TableMismatch] = []
    for table in sorted(source_set - target_set):
        mismatches.append(TableMismatch(table=table, issue="missing_on_target", details="Table exists on source only"))
    for table in sorted(target_set - source_set):
        mismatches.append(TableMismatch(table=table, issue="extra_on_target", details="Table exists on target only"))
    return mismatches
