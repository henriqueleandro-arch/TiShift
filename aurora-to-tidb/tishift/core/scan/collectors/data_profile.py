"""Data profile collector.

Gathers table sizing, BLOB/TEXT column detection, and aggregate totals
from information_schema.
"""

from __future__ import annotations

import logging
from typing import Any

import pymysql

from tishift.models import BlobColumn, DataProfile, TableSize

logger = logging.getLogger(__name__)

_SYSTEM_SCHEMAS = ("mysql", "information_schema", "performance_schema", "sys")
_SCHEMA_FILTER = (
    "table_schema NOT IN ("
    + ", ".join(f"'{s}'" for s in _SYSTEM_SCHEMAS)
    + ")"
)


def collect_data_profile(
    conn: pymysql.Connection,
    database: str | None = None,
) -> DataProfile:
    """Collect data sizing and shape information from the source."""
    profile = DataProfile()

    db_filter = _SCHEMA_FILTER
    params: tuple[str, ...] | None = None
    if database and database != "*":
        db_filter = "table_schema = %s"
        params = (database,)

    with conn.cursor() as cur:
        # ---- Per-table sizing ----
        cur.execute(
            f"""
            SELECT table_schema, table_name, table_rows,
                   ROUND(data_length / 1024 / 1024, 2) AS data_mb,
                   ROUND(index_length / 1024 / 1024, 2) AS index_mb,
                   ROUND((data_length + index_length) / 1024 / 1024, 2) AS total_mb
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE' AND {db_filter}
            ORDER BY data_length + index_length DESC
            """,
            params,
        )
        rows: list[dict[str, Any]] = [
            {k.lower(): v for k, v in row.items()} for row in cur.fetchall()
        ]
        profile.table_sizes = [
            TableSize(
                table_schema=r["table_schema"],
                table_name=r["table_name"],
                table_rows=r.get("table_rows") or 0,
                data_mb=float(r.get("data_mb") or 0),
                index_mb=float(r.get("index_mb") or 0),
                total_mb=float(r.get("total_mb") or 0),
            )
            for r in rows
        ]

        # Aggregates
        profile.total_data_mb = sum(t.data_mb for t in profile.table_sizes)
        profile.total_index_mb = sum(t.index_mb for t in profile.table_sizes)
        profile.total_rows = sum(t.table_rows for t in profile.table_sizes)

        logger.info(
            "Data profile: %d tables, %.2f MB data, %d total rows",
            len(profile.table_sizes),
            profile.total_data_mb,
            profile.total_rows,
        )

        # ---- BLOB/TEXT columns ----
        cur.execute(
            f"""
            SELECT table_schema, table_name, column_name, data_type
            FROM information_schema.columns
            WHERE data_type IN ('blob', 'mediumblob', 'longblob',
                                'text', 'mediumtext', 'longtext')
              AND {db_filter}
            """,
            params,
        )
        blob_rows: list[dict[str, Any]] = [
            {k.lower(): v for k, v in row.items()} for row in cur.fetchall()
        ]
        profile.blob_columns = [
            BlobColumn(
                table_schema=r["table_schema"],
                table_name=r["table_name"],
                column_name=r["column_name"],
                data_type=r["data_type"],
            )
            for r in blob_rows
        ]
        logger.info("Found %d BLOB/TEXT columns", len(profile.blob_columns))

    return profile
