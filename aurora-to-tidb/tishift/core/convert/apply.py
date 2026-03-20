"""Apply converted schema to target TiDB."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pymysql

logger = logging.getLogger(__name__)

# Only allow DDL/schema statements — reject DML that modifies data.
_ALLOWED_STMT_PREFIXES = (
    "CREATE ",
    "ALTER ",
    "DROP INDEX",
    "DROP TABLE IF EXISTS",
    "ADD ",
)


def _split_statements(sql: str) -> list[str]:
    """Split SQL into statements, respecting quoted strings and comments.

    Handles semicolons inside single-quoted strings and backtick-quoted
    identifiers, which naive str.split(';') does not.
    """
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_backtick = False
    i = 0
    chars = sql

    while i < len(chars):
        ch = chars[i]

        # Handle escape sequences inside quotes
        if ch == "\\" and (in_single_quote or in_backtick) and i + 1 < len(chars):
            current.append(ch)
            current.append(chars[i + 1])
            i += 2
            continue

        if ch == "'" and not in_backtick:
            in_single_quote = not in_single_quote
        elif ch == "`" and not in_single_quote:
            in_backtick = not in_backtick

        if ch == ";" and not in_single_quote and not in_backtick:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(ch)
        i += 1

    # Handle final statement without trailing semicolon
    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)

    return statements


def _is_allowed_statement(stmt: str) -> bool:
    """Check that a SQL statement is a DDL/schema statement, not DML."""
    # Strip leading comments
    cleaned = re.sub(r"/\*.*?\*/", "", stmt, flags=re.DOTALL).strip()
    cleaned = re.sub(r"--[^\n]*", "", cleaned).strip()
    upper = cleaned.upper()
    return any(upper.startswith(prefix) for prefix in _ALLOWED_STMT_PREFIXES)


def apply_schema(conn: pymysql.Connection, sql_files: list[Path]) -> None:
    """Execute DDL SQL files in order on the target connection.

    Only CREATE, ALTER, DROP INDEX, and ADD statements are allowed.
    Raises ValueError if a non-DDL statement is detected.
    """
    for path in sql_files:
        if not path.exists():
            continue
        sql = path.read_text()
        if not sql.strip():
            continue
        statements = _split_statements(sql)
        with conn.cursor() as cur:
            for stmt in statements:
                if not _is_allowed_statement(stmt):
                    raise ValueError(
                        f"Rejected non-DDL statement in {path.name}: "
                        f"{stmt[:80]}..."
                    )
                cur.execute(stmt)
        conn.commit()
        logger.info("Applied %s (%d statements)", path, len(statements))
