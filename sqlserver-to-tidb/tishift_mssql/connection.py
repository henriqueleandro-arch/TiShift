"""Connection management for SQL Server source and TiDB target."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Generator

import pymssql
import pymysql
import pymysql.cursors

from tishift_mssql.config import SourceConfig, TargetConfig

logger = logging.getLogger(__name__)

_TRANSIENT_ERRORS = {20002, 20003, 20006, 20047}
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.0


def _build_server(source: SourceConfig) -> str:
    if source.instance:
        return f"{source.host}\\{source.instance}"
    return source.host


def _connect_source(source: SourceConfig) -> pymssql.Connection:
    kwargs: dict[str, Any] = {
        "server": _build_server(source),
        "user": source.user,
        "password": source.password,
        "database": source.database if source.database != "*" else "master",
        "port": source.port,
        "as_dict": True,
        "login_timeout": 10,
        "timeout": 300,
    }
    return pymssql.connect(**kwargs)


@contextmanager
def get_source_connection(source: SourceConfig) -> Generator[pymssql.Connection, None, None]:
    """Create SQL Server connection with transient retry and read-only isolation."""
    conn: pymssql.Connection | None = None
    last_error: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            conn = _connect_source(source)
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
            break
        except pymssql.Error as exc:
            last_error = exc
            err_code = getattr(exc, "number", None)
            if err_code not in _TRANSIENT_ERRORS and attempt == _MAX_RETRIES - 1:
                raise
            wait_seconds = _BACKOFF_BASE_SECONDS * (2 ** attempt)
            logger.warning(
                "Transient SQL Server error on attempt %s/%s (%s). Retrying in %.1fs",
                attempt + 1,
                _MAX_RETRIES,
                exc,
                wait_seconds,
            )
            time.sleep(wait_seconds)

    if conn is None:
        raise ConnectionError(
            f"Failed to connect to SQL Server {source.host}:{source.port} after {_MAX_RETRIES} retries"
        ) from last_error

    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_target_connection(target: TargetConfig) -> Generator[pymysql.Connection, None, None]:
    """Create TiDB target connection and enforce read-only mode for scanner operations."""
    kwargs: dict[str, Any] = {
        "host": target.host,
        "port": target.port,
        "user": target.user,
        "password": target.password,
        "database": target.database or None,
        "cursorclass": pymysql.cursors.DictCursor,
        "connect_timeout": 10,
        "read_timeout": 60,
        "write_timeout": 60,
    }
    if target.tls:
        kwargs["ssl"] = {"ssl": True}

    conn = pymysql.connect(**kwargs)
    try:
        with conn.cursor() as cur:
            cur.execute("SET SESSION TRANSACTION READ ONLY")
        yield conn
    finally:
        conn.close()
