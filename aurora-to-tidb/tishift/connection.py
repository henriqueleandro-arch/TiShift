"""Connection manager for Aurora MySQL source connections.

All source connections are read-only — enforced at the session level.
Uses PyMySQL with DictCursor and automatic retry on transient errors.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Generator

import pymysql
import pymysql.cursors

from tishift.config import SourceConfig, TargetConfig

logger = logging.getLogger(__name__)

# PyMySQL error codes considered transient (worth retrying).
_TRANSIENT_ERRORS = {
    2003,  # Can't connect to MySQL server
    2006,  # MySQL server has gone away
    2013,  # Lost connection during query
    1040,  # Too many connections
    1205,  # Lock wait timeout exceeded
    1213,  # Deadlock found
}

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0  # seconds


def _connect_source(source: SourceConfig) -> pymysql.Connection:
    """Open a raw PyMySQL connection to the source."""
    kwargs: dict[str, Any] = {
        "host": source.host,
        "port": source.port,
        "user": source.user,
        "password": source.password,
        "cursorclass": pymysql.cursors.DictCursor,
        "connect_timeout": 10,
        "read_timeout": 300,
        "charset": "utf8mb4",
    }
    if source.database and source.database != "*":
        kwargs["database"] = source.database
    if source.tls:
        kwargs["ssl"] = {"ssl": True}
    return pymysql.connect(**kwargs)


def _connect_target(target: TargetConfig) -> pymysql.Connection:
    """Open a raw PyMySQL connection to the target (TiDB)."""
    kwargs: dict[str, Any] = {
        "host": target.host,
        "port": target.port,
        "user": target.user,
        "password": target.password,
        "cursorclass": pymysql.cursors.DictCursor,
        "connect_timeout": 10,
        "read_timeout": 300,
        "charset": "utf8mb4",
    }
    if target.database:
        kwargs["database"] = target.database
    if target.tls:
        kwargs["ssl"] = {"ssl": True}
    return pymysql.connect(**kwargs)


@contextmanager
def get_source_connection(
    source: SourceConfig,
) -> Generator[pymysql.Connection, None, None]:
    """Context manager that yields a read-only source connection.

    - Enforces ``SET SESSION TRANSACTION READ ONLY`` immediately.
    - Uses DictCursor for all queries.
    - Retries transient connection errors with exponential backoff.
    """
    conn: pymysql.Connection | None = None
    last_err: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            conn = _connect_source(source)
            # Enforce read-only at the session level.
            with conn.cursor() as cur:
                cur.execute("SET SESSION TRANSACTION READ ONLY")
            break
        except pymysql.Error as exc:
            last_err = exc
            err_code = getattr(exc, "args", (None,))[0]
            if err_code not in _TRANSIENT_ERRORS:
                raise
            wait = _BACKOFF_BASE * (2 ** attempt)
            logger.warning(
                "Transient connection error (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                _MAX_RETRIES,
                wait,
                exc,
            )
            time.sleep(wait)

    if conn is None:
        raise ConnectionError(
            f"Failed to connect to {source.host}:{source.port} after "
            f"{_MAX_RETRIES} attempts"
        ) from last_err

    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_target_connection(
    target: TargetConfig,
) -> Generator[pymysql.Connection, None, None]:
    """Context manager that yields a target connection (read/write)."""
    conn: pymysql.Connection | None = None
    last_err: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            conn = _connect_target(target)
            break
        except pymysql.Error as exc:
            last_err = exc
            err_code = getattr(exc, "args", (None,))[0]
            if err_code not in _TRANSIENT_ERRORS:
                raise
            wait = _BACKOFF_BASE * (2 ** attempt)
            logger.warning(
                "Transient target connection error (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                _MAX_RETRIES,
                wait,
                exc,
            )
            time.sleep(wait)

    if conn is None:
        raise ConnectionError(
            f"Failed to connect to {target.host}:{target.port} after "
            f"{_MAX_RETRIES} attempts"
        ) from last_err

    try:
        yield conn
    finally:
        conn.close()
