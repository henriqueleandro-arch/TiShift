"""Schema inventory collector.

Queries information_schema to build a complete picture of the source
database: tables, columns, indexes, foreign keys, routines, triggers,
views, events, partitions, and charset usage.

All queries use parameterized SQL where applicable and exclude system
schemas.
"""

from __future__ import annotations

import logging
from typing import Any

import pymysql

from tishift.models import (
    CharsetUsage,
    ColumnInfo,
    EventInfo,
    ForeignKeyInfo,
    IndexInfo,
    PartitionInfo,
    RoutineInfo,
    SchemaInventory,
    TableInfo,
    TriggerInfo,
    ViewInfo,
)

logger = logging.getLogger(__name__)

_SYSTEM_SCHEMAS = ("mysql", "information_schema", "performance_schema", "sys")

# Build the NOT IN clause safely.  These are fixed literals, not user input.
_SCHEMA_FILTER = (
    "table_schema NOT IN ("
    + ", ".join(f"'{s}'" for s in _SYSTEM_SCHEMAS)
    + ")"
)


def _query(cursor: Any, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    """Execute query and return all rows as dicts with lowercase keys.

    MySQL information_schema returns UPPERCASE column names (e.g.
    TABLE_SCHEMA) regardless of the case used in the SELECT clause.
    We normalize to lowercase for consistent access.
    """
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    return [{k.lower(): v for k, v in row.items()} for row in rows]


def collect_schema(conn: pymysql.Connection, database: str | None = None) -> SchemaInventory:
    """Collect full schema inventory from the source.

    If *database* is provided and is not ``"*"``, only that database is
    scanned.  Otherwise all non-system databases are included.
    """
    inv = SchemaInventory()

    db_filter = _SCHEMA_FILTER
    if database and database != "*":
        db_filter = "table_schema = %s"

    params: tuple[str, ...] | None = None
    if database and database != "*":
        params = (database,)

    with conn.cursor() as cur:
        # ---- Tables ----
        rows = _query(
            cur,
            f"""
            SELECT table_schema, table_name, engine, row_format, table_rows,
                   data_length, index_length, auto_increment, table_collation,
                   create_options
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE' AND {db_filter}
            """,
            params,
        )
        inv.tables = [
            TableInfo(
                table_schema=r["table_schema"],
                table_name=r["table_name"],
                engine=r.get("engine"),
                row_format=r.get("row_format"),
                table_rows=r.get("table_rows") or 0,
                data_length=r.get("data_length") or 0,
                index_length=r.get("index_length") or 0,
                auto_increment=r.get("auto_increment"),
                table_collation=r.get("table_collation"),
                create_options=r.get("create_options"),
            )
            for r in rows
        ]
        logger.info("Collected %d tables", len(inv.tables))

        # ---- Columns ----
        rows = _query(
            cur,
            f"""
            SELECT table_schema, table_name, column_name, ordinal_position,
                   column_default, is_nullable, data_type, column_type,
                   character_set_name, collation_name, column_key, extra,
                   generation_expression
            FROM information_schema.columns
            WHERE {db_filter}
            """,
            params,
        )
        inv.columns = [
            ColumnInfo(
                table_schema=r["table_schema"],
                table_name=r["table_name"],
                column_name=r["column_name"],
                ordinal_position=r["ordinal_position"],
                column_default=r.get("column_default"),
                is_nullable=r["is_nullable"],
                data_type=r["data_type"],
                column_type=r["column_type"],
                character_set_name=r.get("character_set_name"),
                collation_name=r.get("collation_name"),
                column_key=r.get("column_key", ""),
                extra=r.get("extra", ""),
                generation_expression=r.get("generation_expression"),
            )
            for r in rows
        ]
        logger.info("Collected %d columns", len(inv.columns))

        # ---- Indexes ----
        rows = _query(
            cur,
            f"""
            SELECT table_schema, table_name, index_name, non_unique, index_type,
                   GROUP_CONCAT(column_name ORDER BY seq_in_index) as columns
            FROM information_schema.statistics
            WHERE {db_filter}
            GROUP BY table_schema, table_name, index_name, non_unique, index_type
            """,
            params,
        )
        inv.indexes = [
            IndexInfo(
                table_schema=r["table_schema"],
                table_name=r["table_name"],
                index_name=r["index_name"],
                non_unique=r["non_unique"],
                index_type=r.get("index_type", ""),
                columns=r.get("columns", ""),
            )
            for r in rows
        ]
        logger.info("Collected %d indexes", len(inv.indexes))

        # ---- Foreign Keys ----
        fk_filter = db_filter.replace("table_schema", "constraint_schema")
        fk_params = params
        rows = _query(
            cur,
            f"""
            SELECT constraint_schema, table_name, constraint_name,
                   referenced_table_schema, referenced_table_name,
                   GROUP_CONCAT(column_name) as columns,
                   GROUP_CONCAT(referenced_column_name) as ref_columns
            FROM information_schema.key_column_usage
            WHERE referenced_table_name IS NOT NULL AND {fk_filter}
            GROUP BY constraint_schema, table_name, constraint_name,
                     referenced_table_schema, referenced_table_name
            """,
            fk_params,
        )
        inv.foreign_keys = [
            ForeignKeyInfo(
                constraint_schema=r["constraint_schema"],
                table_name=r["table_name"],
                constraint_name=r["constraint_name"],
                referenced_table_schema=r.get("referenced_table_schema"),
                referenced_table_name=r.get("referenced_table_name"),
                columns=r.get("columns", ""),
                ref_columns=r.get("ref_columns", ""),
            )
            for r in rows
        ]
        logger.info("Collected %d foreign keys", len(inv.foreign_keys))

        # ---- Routines (Stored Procedures & Functions) ----
        rtn_filter = db_filter.replace("table_schema", "routine_schema")
        rtn_params = params
        rows = _query(
            cur,
            f"""
            SELECT routine_schema, routine_name, routine_type, data_type,
                   routine_body, routine_definition, is_deterministic,
                   security_type, definer
            FROM information_schema.routines
            WHERE {rtn_filter}
            """,
            rtn_params,
        )
        inv.routines = [
            RoutineInfo(
                routine_schema=r["routine_schema"],
                routine_name=r["routine_name"],
                routine_type=r["routine_type"],
                data_type=r.get("data_type"),
                routine_body=r.get("routine_body"),
                routine_definition=r.get("routine_definition"),
                is_deterministic=r.get("is_deterministic", "NO"),
                security_type=r.get("security_type", "DEFINER"),
                definer=r.get("definer"),
            )
            for r in rows
        ]
        logger.info("Collected %d routines", len(inv.routines))

        # ---- Triggers ----
        trg_filter = db_filter.replace("table_schema", "trigger_schema")
        trg_params = params
        rows = _query(
            cur,
            f"""
            SELECT trigger_schema, trigger_name, event_manipulation,
                   event_object_table, action_statement, action_timing
            FROM information_schema.triggers
            WHERE {trg_filter}
            """,
            trg_params,
        )
        inv.triggers = [
            TriggerInfo(
                trigger_schema=r["trigger_schema"],
                trigger_name=r["trigger_name"],
                event_manipulation=r["event_manipulation"],
                event_object_table=r["event_object_table"],
                action_statement=r.get("action_statement"),
                action_timing=r["action_timing"],
            )
            for r in rows
        ]
        logger.info("Collected %d triggers", len(inv.triggers))

        # ---- Views ----
        rows = _query(
            cur,
            f"""
            SELECT table_schema, table_name, view_definition, check_option,
                   is_updatable, definer, security_type
            FROM information_schema.views
            WHERE {db_filter}
            """,
            params,
        )
        inv.views = [
            ViewInfo(
                table_schema=r["table_schema"],
                table_name=r["table_name"],
                view_definition=r.get("view_definition"),
                check_option=r.get("check_option"),
                is_updatable=r.get("is_updatable", "NO"),
                definer=r.get("definer"),
                security_type=r.get("security_type"),
            )
            for r in rows
        ]
        logger.info("Collected %d views", len(inv.views))

        # ---- Events ----
        evt_filter = db_filter.replace("table_schema", "event_schema")
        evt_params = params
        rows = _query(
            cur,
            f"""
            SELECT event_schema, event_name, event_type, execute_at,
                   interval_value, interval_field, event_definition, status
            FROM information_schema.events
            WHERE {evt_filter}
            """,
            evt_params,
        )
        inv.events = [
            EventInfo(
                event_schema=r["event_schema"],
                event_name=r["event_name"],
                event_type=r["event_type"],
                execute_at=str(r["execute_at"]) if r.get("execute_at") else None,
                interval_value=str(r["interval_value"]) if r.get("interval_value") else None,
                interval_field=r.get("interval_field"),
                event_definition=r.get("event_definition"),
                status=r.get("status", ""),
            )
            for r in rows
        ]
        logger.info("Collected %d events", len(inv.events))

        # ---- Partitions ----
        rows = _query(
            cur,
            f"""
            SELECT table_schema, table_name, partition_name, partition_method,
                   partition_expression, partition_description,
                   subpartition_method, subpartition_expression
            FROM information_schema.partitions
            WHERE partition_name IS NOT NULL AND {db_filter}
            """,
            params,
        )
        inv.partitions = [
            PartitionInfo(
                table_schema=r["table_schema"],
                table_name=r["table_name"],
                partition_name=r.get("partition_name"),
                partition_method=r.get("partition_method"),
                partition_expression=r.get("partition_expression"),
                partition_description=r.get("partition_description"),
                subpartition_method=r.get("subpartition_method"),
                subpartition_expression=r.get("subpartition_expression"),
            )
            for r in rows
        ]
        logger.info("Collected %d partitions", len(inv.partitions))

        # ---- Character Set Usage ----
        rows = _query(
            cur,
            f"""
            SELECT character_set_name, collation_name,
                   COUNT(*) as column_count
            FROM information_schema.columns
            WHERE {db_filter}
              AND character_set_name IS NOT NULL
            GROUP BY character_set_name, collation_name
            """,
            params,
        )
        inv.charset_usage = [
            CharsetUsage(
                character_set_name=r.get("character_set_name"),
                collation_name=r.get("collation_name"),
                column_count=r.get("column_count", 0),
            )
            for r in rows
        ]
        logger.info("Collected %d charset/collation combos", len(inv.charset_usage))

    return inv
