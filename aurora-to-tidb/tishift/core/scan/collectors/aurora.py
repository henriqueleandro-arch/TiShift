"""Aurora-specific metadata collector.

Reads server variables relevant to migration planning: Aurora version,
binlog format, character set, sql_mode, etc.

Wraps @@aurora_version in try/except so the tool works against plain
MySQL/RDS MySQL too.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pymysql

from tishift.models import AuroraMetadata

logger = logging.getLogger(__name__)


def _get_var(cursor: Any, expr: str) -> str | None:
    """Execute ``SELECT <expr>`` and return the scalar value, or None.

    Only @@system_variable expressions are allowed to prevent SQL injection.
    """
    if not re.fullmatch(r"@@[a-zA-Z_][a-zA-Z0-9_.]*", expr):
        raise ValueError(f"Only @@system_variable expressions are allowed, got: {expr!r}")
    try:
        cursor.execute(f"SELECT {expr}")
        row = cursor.fetchone()
        if row is None:
            return None
        # DictCursor returns {col_alias: value}
        return str(list(row.values())[0]) if row else None
    except pymysql.Error:
        return None


def collect_aurora_metadata(conn: pymysql.Connection) -> AuroraMetadata:
    """Collect Aurora/MySQL server metadata."""
    meta = AuroraMetadata()

    with conn.cursor() as cur:
        # Aurora-specific — will fail on plain MySQL/RDS MySQL.
        meta.aurora_version = _get_var(cur, "@@aurora_version")

        # Standard MySQL variables.
        meta.mysql_version = _get_var(cur, "@@version")
        meta.version_comment = _get_var(cur, "@@version_comment")
        meta.binlog_format = _get_var(cur, "@@binlog_format")
        meta.binlog_row_image = _get_var(cur, "@@binlog_row_image")
        meta.character_set_server = _get_var(cur, "@@character_set_server")
        meta.collation_server = _get_var(cur, "@@collation_server")
        meta.transaction_isolation = _get_var(cur, "@@transaction_isolation")
        meta.sql_mode = _get_var(cur, "@@sql_mode")

        max_conn = _get_var(cur, "@@max_connections")
        meta.max_connections = int(max_conn) if max_conn else None

        pool_size = _get_var(cur, "@@innodb_buffer_pool_size")
        meta.innodb_buffer_pool_size = int(pool_size) if pool_size else None

        lc_names = _get_var(cur, "@@lower_case_table_names")
        meta.lower_case_table_names = int(lc_names) if lc_names else None

        meta.explicit_defaults_for_timestamp = _get_var(
            cur, "@@explicit_defaults_for_timestamp"
        )

    logger.info(
        "Aurora metadata: version=%s, mysql=%s, binlog=%s, charset=%s",
        meta.aurora_version or "N/A (plain MySQL)",
        meta.mysql_version,
        meta.binlog_format,
        meta.character_set_server,
    )
    return meta
