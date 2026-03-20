"""Row count checker."""

from __future__ import annotations

from tishift_mssql.check.models import TableMismatch


def compare_counts(source_counts: dict[str, int], target_counts: dict[str, int]) -> list[TableMismatch]:
    """Compare table row counts."""
    mismatches: list[TableMismatch] = []
    for table, source_count in source_counts.items():
        target_count = target_counts.get(table)
        if target_count is None:
            continue
        if int(source_count) != int(target_count):
            mismatches.append(
                TableMismatch(
                    table=table,
                    issue="row_count",
                    details=f"source={source_count} target={target_count}",
                )
            )
    return mismatches
