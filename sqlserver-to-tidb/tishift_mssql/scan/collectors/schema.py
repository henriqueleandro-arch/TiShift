"""Schema inventory collector for SQL Server."""

from __future__ import annotations

from collections import defaultdict

import pymssql

from tishift_mssql.models import (
    AgentJobInfo,
    AssemblyInfo,
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    LinkedServerInfo,
    RoutineInfo,
    SchemaInventory,
    TableInfo,
    TriggerInfo,
    ViewInfo,
)


_VALID_DB_NAME = __import__("re").compile(r"^[A-Za-z0-9_$#@][A-Za-z0-9_$#@ .\-]{0,127}$")


def _safe_use_db(cur: "pymssql.Cursor", database: str) -> None:
    """Switch database context with identifier validation."""
    if not _VALID_DB_NAME.match(database):
        raise ValueError(f"Invalid database name: {database!r}")
    cur.execute("USE [%s]" % database.replace("]", "]]"))


def _as_bool(value: object) -> bool:
    return bool(value) if value is not None else False


def collect_schema(conn: pymssql.Connection, database: str | None) -> SchemaInventory:
    """Collect SQL Server schema objects from sys catalogs."""
    inventory = SchemaInventory()

    if database and database != "*":
        with conn.cursor() as cur:
            _safe_use_db(cur, database)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.name AS schema_name, t.name AS table_name,
                   SUM(CASE WHEN p.index_id IN (0,1) THEN p.rows ELSE 0 END) AS row_count,
                   SUM(a.total_pages) * 8.0 / 1024.0 AS total_mb,
                   SUM(a.used_pages) * 8.0 / 1024.0 AS used_mb,
                   t.is_memory_optimized,
                   CASE WHEN t.temporal_type > 0 THEN 1 ELSE 0 END AS is_temporal,
                   CASE WHEN EXISTS (
                        SELECT 1 FROM sys.indexes i
                        WHERE i.object_id = t.object_id AND i.index_id = 0
                   ) THEN 1 ELSE 0 END AS is_heap
            FROM sys.tables t
            JOIN sys.schemas s ON s.schema_id = t.schema_id
            LEFT JOIN sys.partitions p ON p.object_id = t.object_id
            LEFT JOIN sys.allocation_units a ON a.container_id = p.partition_id
            GROUP BY s.name, t.name, t.is_memory_optimized, t.temporal_type
            ORDER BY s.name, t.name
            """
        )
        for row in cur.fetchall():
            inventory.tables.append(
                TableInfo(
                    schema_name=row["schema_name"],
                    table_name=row["table_name"],
                    row_count=int(row.get("row_count") or 0),
                    total_mb=float(row.get("total_mb") or 0.0),
                    used_mb=float(row.get("used_mb") or 0.0),
                    is_memory_optimized=_as_bool(row.get("is_memory_optimized")),
                    is_temporal=_as_bool(row.get("is_temporal")),
                    is_heap=_as_bool(row.get("is_heap")),
                )
            )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.name AS schema_name, t.name AS table_name,
                   c.name AS column_name, c.column_id,
                   ty.name AS data_type, c.max_length,
                   c.precision, c.scale,
                   c.is_nullable, c.is_identity, c.is_computed,
                   c.is_filestream,
                   c.collation_name, cc.definition AS computed_definition,
                   dc.definition AS default_definition
            FROM sys.columns c
            JOIN sys.tables t ON t.object_id = c.object_id
            JOIN sys.schemas s ON s.schema_id = t.schema_id
            JOIN sys.types ty ON ty.user_type_id = c.user_type_id
            LEFT JOIN sys.computed_columns cc ON cc.object_id = c.object_id AND cc.column_id = c.column_id
            LEFT JOIN sys.default_constraints dc ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
            ORDER BY s.name, t.name, c.column_id
            """
        )
        for row in cur.fetchall():
            inventory.columns.append(
                ColumnInfo(
                    schema_name=row["schema_name"],
                    table_name=row["table_name"],
                    column_name=row["column_name"],
                    ordinal_position=int(row["column_id"]),
                    data_type=row["data_type"],
                    max_length=row.get("max_length"),
                    precision=row.get("precision"),
                    scale=row.get("scale"),
                    is_nullable=_as_bool(row.get("is_nullable")),
                    is_identity=_as_bool(row.get("is_identity")),
                    is_computed=_as_bool(row.get("is_computed")),
                    collation_name=row.get("collation_name"),
                    computed_definition=row.get("computed_definition"),
                    default_definition=row.get("default_definition"),
                    is_filestream=_as_bool(row.get("is_filestream")),
                )
            )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.name AS schema_name,
                   t.name AS table_name,
                   i.name AS index_name,
                   i.type_desc AS index_type,
                   i.is_unique,
                   i.is_primary_key,
                   i.filter_definition,
                   c.name AS column_name,
                   ic.is_included_column,
                   ic.key_ordinal
            FROM sys.indexes i
            JOIN sys.tables t ON t.object_id = i.object_id
            JOIN sys.schemas s ON s.schema_id = t.schema_id
            JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
            JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
            WHERE i.name IS NOT NULL
            ORDER BY s.name, t.name, i.name, ic.key_ordinal
            """
        )
        grouped: dict[tuple[str, str, str], dict[str, object]] = {}
        for row in cur.fetchall():
            key = (row["schema_name"], row["table_name"], row["index_name"])
            if key not in grouped:
                grouped[key] = {
                    "index_type": row["index_type"],
                    "is_unique": _as_bool(row.get("is_unique")),
                    "is_primary_key": _as_bool(row.get("is_primary_key")),
                    "filter_definition": row.get("filter_definition"),
                    "columns": [],
                    "included": [],
                }
            if _as_bool(row.get("is_included_column")):
                grouped[key]["included"].append(row["column_name"])
            else:
                grouped[key]["columns"].append(row["column_name"])

        for (schema_name, table_name, index_name), agg in grouped.items():
            inventory.indexes.append(
                IndexInfo(
                    schema_name=schema_name,
                    table_name=table_name,
                    index_name=index_name,
                    index_type=str(agg["index_type"]),
                    is_unique=bool(agg["is_unique"]),
                    is_primary_key=bool(agg["is_primary_key"]),
                    columns=",".join(agg["columns"]),
                    included_columns=",".join(agg["included"]),
                    filter_definition=agg["filter_definition"],
                )
            )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT sch.name AS schema_name,
                   parent.name AS table_name,
                   fk.name AS fk_name,
                   sch_ref.name AS referenced_schema_name,
                   ref.name AS referenced_table_name,
                   c_parent.name AS parent_col,
                   c_ref.name AS ref_col,
                   fk.delete_referential_action_desc AS delete_action,
                   fk.update_referential_action_desc AS update_action,
                   fkc.constraint_column_id
            FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
            JOIN sys.tables parent ON parent.object_id = fk.parent_object_id
            JOIN sys.schemas sch ON sch.schema_id = parent.schema_id
            JOIN sys.tables ref ON ref.object_id = fk.referenced_object_id
            JOIN sys.schemas sch_ref ON sch_ref.schema_id = ref.schema_id
            JOIN sys.columns c_parent ON c_parent.object_id = fkc.parent_object_id AND c_parent.column_id = fkc.parent_column_id
            JOIN sys.columns c_ref ON c_ref.object_id = fkc.referenced_object_id AND c_ref.column_id = fkc.referenced_column_id
            ORDER BY sch.name, parent.name, fk.name, fkc.constraint_column_id
            """
        )
        grouped_fk: dict[tuple[str, str, str], dict[str, object]] = defaultdict(
            lambda: {
                "ref_schema": "",
                "ref_table": "",
                "delete_action": "",
                "update_action": "",
                "cols": [],
                "ref_cols": [],
            }
        )
        for row in cur.fetchall():
            key = (row["schema_name"], row["table_name"], row["fk_name"])
            grp = grouped_fk[key]
            grp["ref_schema"] = row["referenced_schema_name"]
            grp["ref_table"] = row["referenced_table_name"]
            grp["delete_action"] = row["delete_action"]
            grp["update_action"] = row["update_action"]
            grp["cols"].append(row["parent_col"])
            grp["ref_cols"].append(row["ref_col"])

        for (schema_name, table_name, fk_name), grp in grouped_fk.items():
            inventory.foreign_keys.append(
                ForeignKeyInfo(
                    schema_name=schema_name,
                    table_name=table_name,
                    fk_name=fk_name,
                    referenced_schema_name=str(grp["ref_schema"]),
                    referenced_table_name=str(grp["ref_table"]),
                    columns=",".join(grp["cols"]),
                    referenced_columns=",".join(grp["ref_cols"]),
                    delete_action=str(grp["delete_action"]),
                    update_action=str(grp["update_action"]),
                )
            )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.name AS schema_name,
                   o.name AS routine_name,
                   o.type_desc AS routine_type,
                   m.definition,
                   CASE WHEN am.object_id IS NOT NULL THEN 1 ELSE 0 END AS is_clr,
                   a.name AS assembly_name
            FROM sys.objects o
            JOIN sys.schemas s ON s.schema_id = o.schema_id
            LEFT JOIN sys.sql_modules m ON m.object_id = o.object_id
            LEFT JOIN sys.assembly_modules am ON am.object_id = o.object_id
            LEFT JOIN sys.assemblies a ON a.assembly_id = am.assembly_id
            WHERE o.type IN ('P', 'FN', 'IF', 'TF')
            ORDER BY s.name, o.name
            """
        )
        for row in cur.fetchall():
            inventory.routines.append(
                RoutineInfo(
                    schema_name=row["schema_name"],
                    routine_name=row["routine_name"],
                    routine_type=row["routine_type"],
                    definition=row.get("definition"),
                    is_clr=_as_bool(row.get("is_clr")),
                    assembly_name=row.get("assembly_name"),
                )
            )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.name AS schema_name,
                   tr.name AS trigger_name,
                   tbl.name AS table_name,
                   tr.is_instead_of_trigger,
                   CASE WHEN am.object_id IS NOT NULL THEN 1 ELSE 0 END AS is_clr,
                   m.definition
            FROM sys.triggers tr
            LEFT JOIN sys.tables tbl ON tbl.object_id = tr.parent_id
            LEFT JOIN sys.schemas s ON s.schema_id = COALESCE(tbl.schema_id, tr.schema_id)
            LEFT JOIN sys.sql_modules m ON m.object_id = tr.object_id
            LEFT JOIN sys.assembly_modules am ON am.object_id = tr.object_id
            ORDER BY s.name, tr.name
            """
        )
        for row in cur.fetchall():
            inventory.triggers.append(
                TriggerInfo(
                    schema_name=row.get("schema_name") or "dbo",
                    trigger_name=row["trigger_name"],
                    table_name=row.get("table_name"),
                    is_instead_of=_as_bool(row.get("is_instead_of_trigger")),
                    is_clr=_as_bool(row.get("is_clr")),
                    definition=row.get("definition"),
                )
            )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.name AS schema_name,
                   v.name AS view_name,
                   m.definition,
                   CASE WHEN idx.object_id IS NULL THEN 0 ELSE 1 END AS is_indexed,
                   CASE WHEN m.definition LIKE '%WITH SCHEMABINDING%' THEN 1 ELSE 0 END AS with_schemabinding
            FROM sys.views v
            JOIN sys.schemas s ON s.schema_id = v.schema_id
            LEFT JOIN sys.sql_modules m ON m.object_id = v.object_id
            LEFT JOIN (
                SELECT DISTINCT object_id FROM sys.indexes WHERE index_id > 0
            ) idx ON idx.object_id = v.object_id
            ORDER BY s.name, v.name
            """
        )
        for row in cur.fetchall():
            inventory.views.append(
                ViewInfo(
                    schema_name=row["schema_name"],
                    view_name=row["view_name"],
                    definition=row.get("definition"),
                    is_indexed=_as_bool(row.get("is_indexed")),
                    with_schemabinding=_as_bool(row.get("with_schemabinding")),
                )
            )

    with conn.cursor() as cur:
        cur.execute(
            "SELECT name AS assembly_name, permission_set_desc AS permission_set, clr_name FROM sys.assemblies"
        )
        for row in cur.fetchall():
            inventory.assemblies.append(
                AssemblyInfo(
                    assembly_name=row["assembly_name"],
                    permission_set=row["permission_set"],
                    clr_name=row.get("clr_name"),
                )
            )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT name AS server_name,
                   product,
                   provider,
                   data_source
            FROM sys.servers
            WHERE server_id > 0
            ORDER BY name
            """
        )
        for row in cur.fetchall():
            inventory.linked_servers.append(
                LinkedServerInfo(
                    server_name=row["server_name"],
                    product=row.get("product"),
                    provider=row.get("provider"),
                    data_source=row.get("data_source"),
                )
            )

    # Optional; may fail if msdb access is denied.
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name AS job_name, enabled, description
                FROM msdb.dbo.sysjobs
                ORDER BY name
                """
            )
            for row in cur.fetchall():
                inventory.agent_jobs.append(
                    AgentJobInfo(
                        job_name=row["job_name"],
                        enabled=_as_bool(row.get("enabled")),
                        description=row.get("description"),
                    )
                )
    except pymssql.Error as exc:
        import logging
        logging.getLogger(__name__).warning("Could not read SQL Agent jobs (msdb access): %s", exc)

    with conn.cursor() as cur:
        cur.execute("SELECT name FROM sys.partition_functions ORDER BY name")
        inventory.partition_functions = [row["name"] for row in cur.fetchall()]

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.name, COUNT(t.object_id) AS table_count
            FROM sys.schemas s
            LEFT JOIN sys.tables t ON s.schema_id = t.schema_id
            WHERE s.name NOT IN ('sys', 'INFORMATION_SCHEMA', 'guest', 'db_owner',
                                  'db_accessadmin', 'db_securityadmin', 'db_ddladmin',
                                  'db_backupoperator', 'db_datareader', 'db_datawriter',
                                  'db_denydatareader', 'db_denydatawriter')
            GROUP BY s.name
            HAVING COUNT(t.object_id) > 0 OR s.name = 'dbo'
            ORDER BY s.name
            """
        )
        inventory.schemas = [row["name"] for row in cur.fetchall()]

    return inventory
