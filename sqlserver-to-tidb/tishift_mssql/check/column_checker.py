"""Column compatibility checker."""

from __future__ import annotations

from tishift_mssql.check.models import TableMismatch


def compare_columns(
    source_columns: dict[str, dict[str, str]],
    target_columns: dict[str, dict[str, str]],
) -> list[TableMismatch]:
    """Compare per-table column signatures."""
    mismatches: list[TableMismatch] = []
    for table, cols in source_columns.items():
        if table not in target_columns:
            continue
        target = target_columns[table]
        for col_name, col_type in cols.items():
            tgt_type = target.get(col_name)
            if tgt_type is None:
                mismatches.append(TableMismatch(table, "missing_column", f"Missing column on target: {col_name}"))
            elif tgt_type.lower() != col_type.lower():
                mismatches.append(TableMismatch(table, "column_type", f"{col_name}: source={col_type} target={tgt_type}"))
    return mismatches
