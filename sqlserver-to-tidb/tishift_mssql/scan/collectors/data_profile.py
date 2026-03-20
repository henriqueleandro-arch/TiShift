"""Data profile collector for size and row distribution."""

from __future__ import annotations

import pymssql

from tishift_mssql.models import DataProfile, TableSize


def collect_data_profile(conn: pymssql.Connection, database: str | None) -> DataProfile:
    """Collect table sizing and row counts from DMVs."""
    if database and database != "*":
        from tishift_mssql.scan.collectors.schema import _safe_use_db
        with conn.cursor() as cur:
            _safe_use_db(cur, database)

    profile = DataProfile()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.name AS schema_name,
                   t.name AS table_name,
                   SUM(ps.row_count) AS row_count,
                   SUM(ps.reserved_page_count) * 8.0 / 1024.0 AS reserved_mb,
                   SUM(ps.in_row_data_page_count + ps.lob_used_page_count + ps.row_overflow_used_page_count) * 8.0 / 1024.0 AS data_mb,
                   (SUM(ps.used_page_count) - SUM(ps.in_row_data_page_count + ps.lob_used_page_count + ps.row_overflow_used_page_count)) * 8.0 / 1024.0 AS index_mb
            FROM sys.dm_db_partition_stats ps
            JOIN sys.tables t ON t.object_id = ps.object_id
            JOIN sys.schemas s ON s.schema_id = t.schema_id
            GROUP BY s.name, t.name
            ORDER BY reserved_mb DESC
            """
        )
        for row in cur.fetchall():
            table = TableSize(
                schema_name=row["schema_name"],
                table_name=row["table_name"],
                row_count=int(row.get("row_count") or 0),
                reserved_mb=float(row.get("reserved_mb") or 0.0),
                data_mb=float(row.get("data_mb") or 0.0),
                index_mb=float(row.get("index_mb") or 0.0),
            )
            profile.table_sizes.append(table)
            profile.total_rows += table.row_count
            profile.total_data_mb += table.data_mb
            profile.total_index_mb += table.index_mb

    return profile
