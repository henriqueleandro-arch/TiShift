"""SQL Server metadata collector."""

from __future__ import annotations

import pymssql

from tishift_mssql.models import SQLServerMetadata


def collect_sqlserver_metadata(conn: pymssql.Connection) -> SQLServerMetadata:
    """Collect instance and DB-level metadata used by analyzers."""
    metadata = SQLServerMetadata()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT @@VERSION AS version_text,
                   CAST(SERVERPROPERTY('Edition') AS NVARCHAR(128)) AS edition,
                   CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(128)) AS product_version,
                   CAST(SERVERPROPERTY('EngineEdition') AS INT) AS engine_edition
            """
        )
        row = cur.fetchone() or {}
        metadata.version = row.get("version_text")
        metadata.edition = row.get("edition")
        metadata.product_version = row.get("product_version")
        metadata.engine_edition = row.get("engine_edition")

    with conn.cursor() as cur:
        cur.execute("SELECT name, value_in_use FROM sys.configurations")
        metadata.configuration = {
            str(row["name"]): str(row.get("value_in_use"))
            for row in cur.fetchall()
        }

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.collation_name,
                   d.is_cdc_enabled,
                   SUM(mf.size) * 8.0 / 1024.0 AS db_size_mb
            FROM sys.databases d
            JOIN sys.master_files mf ON mf.database_id = d.database_id
            WHERE d.name = DB_NAME()
            GROUP BY d.collation_name, d.is_cdc_enabled
            """
        )
        row = cur.fetchone() or {}
        metadata.db_collation = row.get("collation_name")
        metadata.cdc_enabled = bool(row.get("is_cdc_enabled"))
        metadata.db_size_mb = float(row.get("db_size_mb") or 0.0)

    with conn.cursor() as cur:
        cur.execute("SELECT cpu_count FROM sys.dm_os_sys_info")
        row = cur.fetchone() or {}
        metadata.cpu_count = row.get("cpu_count")

    # SSIS detection via SSISDB existence
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DB_ID('SSISDB') AS ssisdb_id")
            row = cur.fetchone() or {}
            metadata.has_ssis = row.get("ssisdb_id") is not None
    except Exception:
        metadata.has_ssis = False

    # Authentication mode
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT CAST(SERVERPROPERTY('IsIntegratedSecurityOnly') AS INT) AS windows_only"
            )
            row = cur.fetchone() or {}
            if row.get("windows_only") == 1:
                metadata.auth_mode = "windows"
    except Exception:
        pass

    return metadata
