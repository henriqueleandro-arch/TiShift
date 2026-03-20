"""Table structure and row count comparison."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pymysql

logger = logging.getLogger(__name__)


@dataclass
class TableComparison:
    table_schema: str
    table_name: str
    source_rows: int
    target_rows: int
    row_count_match: bool


@dataclass
class ColumnComparison:
    table_schema: str
    table_name: str
    column_name: str
    source_type: str
    target_type: str
    match: bool


def _fetch_row_counts(conn: pymysql.Connection, schema: str) -> dict[str, int]:
    sql = (
        "SELECT table_name, table_rows FROM information_schema.tables "
        "WHERE table_schema = %s"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (schema,))
        rows = cur.fetchall()
    return {r["table_name"]: int(r["table_rows"] or 0) for r in rows}


def compare_row_counts(
    source_conn: pymysql.Connection,
    target_conn: pymysql.Connection,
    schema: str,
) -> list[TableComparison]:
    """Compare row counts between source and target for a schema."""
    source_counts = _fetch_row_counts(source_conn, schema)
    target_counts = _fetch_row_counts(target_conn, schema)

    comparisons: list[TableComparison] = []
    for table, source_rows in source_counts.items():
        target_rows = target_counts.get(table, 0)
        comparisons.append(
            TableComparison(
                table_schema=schema,
                table_name=table,
                source_rows=source_rows,
                target_rows=target_rows,
                row_count_match=source_rows == target_rows,
            )
        )
    logger.info("Row count comparison complete for %s", schema)
    return comparisons


def _fetch_columns(conn: pymysql.Connection, schema: str) -> dict[str, dict[str, str]]:
    sql = (
        "SELECT table_name, column_name, column_type FROM information_schema.columns "
        "WHERE table_schema = %s"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (schema,))
        rows = cur.fetchall()

    tables: dict[str, dict[str, str]] = {}
    for row in rows:
        tables.setdefault(row["table_name"], {})[row["column_name"]] = row["column_type"]
    return tables


def compare_table_structures(
    source_conn: pymysql.Connection,
    target_conn: pymysql.Connection,
    schema: str,
) -> list[ColumnComparison]:
    """Compare column types between source and target."""
    source_cols = _fetch_columns(source_conn, schema)
    target_cols = _fetch_columns(target_conn, schema)

    comparisons: list[ColumnComparison] = []
    for table, cols in source_cols.items():
        target = target_cols.get(table, {})
        for col_name, col_type in cols.items():
            target_type = target.get(col_name)
            comparisons.append(
                ColumnComparison(
                    table_schema=schema,
                    table_name=table,
                    column_name=col_name,
                    source_type=col_type,
                    target_type=target_type or "",
                    match=col_type == (target_type or ""),
                )
            )
    logger.info("Table structure comparison complete for %s", schema)
    return comparisons
