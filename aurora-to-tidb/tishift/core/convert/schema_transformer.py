"""Schema transformer for Aurora MySQL -> TiDB DDL."""

from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass, field
from typing import Iterable

from tishift.core.rules.tidb_compat import SPATIAL_TYPES, UNSUPPORTED_COLLATIONS
from tishift.models import (
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    PartitionInfo,
    SchemaInventory,
    TableInfo,
    ViewInfo,
)

logger = logging.getLogger(__name__)

_SPATIAL_TYPES = SPATIAL_TYPES


@dataclass
class SchemaConversionResult:
    create_tables_sql: str
    create_indexes_sql: str
    create_views_sql: str
    foreign_keys_sql: str
    conversion_notes: list[str] = field(default_factory=list)
    events_notes: list[str] = field(default_factory=list)
    original_schema_sql: str = ""


@dataclass
class TransformOptions:
    target_is_cloud: bool = True
    default_collation: str = "utf8mb4_general_ci"


def _quote_identifier(name: str) -> str:
    return f"`{name}`"


def _format_default(value: str | None) -> str | None:
    if value is None:
        return None
    val = value.strip()
    if not val:
        return None
    upper = val.upper()
    if upper in ("CURRENT_TIMESTAMP", "NULL"):
        return val
    if re.match(r"^-?\d+(\.\d+)?$", val):
        return val
    if val.startswith("(") and val.endswith(")"):
        return val
    return f"'{val}'"


def _group_by_table(items: Iterable, key_attr: str = "table_name") -> dict[str, list]:
    grouped: dict[str, list] = {}
    for item in items:
        key = getattr(item, key_attr)
        grouped.setdefault(key, []).append(item)
    return grouped


def _apply_collation(collation: str | None, options: TransformOptions, notes: list[str]) -> str | None:
    if not collation:
        return None
    if collation.lower() in UNSUPPORTED_COLLATIONS:
        notes.append(f"Mapped unsupported collation {collation} -> {options.default_collation}")
        return options.default_collation
    return collation


def _convert_column(
    col: ColumnInfo,
    options: TransformOptions,
    notes: list[str],
    apply_rules: bool,
) -> str:
    col_type = col.column_type
    if apply_rules and col.data_type.lower() in _SPATIAL_TYPES:
        notes.append(
            f"Spatial column {col.table_schema}.{col.table_name}.{col.column_name} converted to JSON"
        )
        col_type = "json"

    line = f"{_quote_identifier(col.column_name)} {col_type}"

    if col.generation_expression:
        line += f" GENERATED ALWAYS AS ({col.generation_expression})"
        if "VIRTUAL" in col.extra.upper():
            line += " VIRTUAL"
        elif "STORED" in col.extra.upper():
            line += " STORED"

    if col.is_nullable.upper() == "NO":
        line += " NOT NULL"

    default = _format_default(col.column_default)
    if default is not None:
        line += f" DEFAULT {default}"

    if "auto_increment" in col.extra.lower():
        line += " AUTO_INCREMENT"

    return line


def _build_primary_key(indexes: list[IndexInfo]) -> str | None:
    for idx in indexes:
        if idx.index_name.upper() == "PRIMARY":
            cols = ", ".join(_quote_identifier(c.strip()) for c in idx.columns.split(","))
            return f"PRIMARY KEY ({cols})"
    return None


def _build_indexes(indexes: list[IndexInfo], options: TransformOptions, notes: list[str]) -> tuple[list[str], list[str]]:
    create_sql: list[str] = []
    fulltext_removed: list[str] = []

    for idx in indexes:
        if idx.index_name.upper() == "PRIMARY":
            continue
        if idx.index_type.upper() == "FULLTEXT" and not options.target_is_cloud:
            fulltext_removed.append(f"{idx.table_schema}.{idx.table_name}.{idx.index_name}")
            continue
        cols = ", ".join(_quote_identifier(c.strip()) for c in idx.columns.split(","))
        unique = "UNIQUE " if idx.non_unique == 0 else ""
        create_sql.append(
            f"CREATE {unique}INDEX {_quote_identifier(idx.index_name)} ON "
            f"{_quote_identifier(idx.table_schema)}.{_quote_identifier(idx.table_name)} ({cols});"
        )

    if fulltext_removed:
        notes.append(
            "Removed FULLTEXT indexes for self-hosted TiDB: " + ", ".join(fulltext_removed)
        )
    return create_sql, fulltext_removed


def _build_foreign_keys(fks: list[ForeignKeyInfo]) -> list[str]:
    stmts: list[str] = []
    for fk in fks:
        cols = ", ".join(_quote_identifier(c.strip()) for c in fk.columns.split(","))
        ref_cols = ", ".join(_quote_identifier(c.strip()) for c in fk.ref_columns.split(","))
        stmts.append(
            f"ALTER TABLE {_quote_identifier(fk.constraint_schema)}.{_quote_identifier(fk.table_name)} "
            f"ADD CONSTRAINT {_quote_identifier(fk.constraint_name)} "
            f"FOREIGN KEY ({cols}) REFERENCES {_quote_identifier(fk.referenced_table_schema)}." \
            f"{_quote_identifier(fk.referenced_table_name)} ({ref_cols});"
        )
    return stmts


def _build_partitions(partitions: list[PartitionInfo]) -> str:
    if not partitions:
        return ""
    first = partitions[0]
    if not first.partition_method or not first.partition_expression:
        return ""

    parts = []
    for p in partitions:
        if not p.partition_name:
            continue
        desc = p.partition_description or "MAXVALUE"
        parts.append(f"PARTITION {_quote_identifier(p.partition_name)} VALUES LESS THAN ({desc})")
    if not parts:
        return ""

    return (
        f"PARTITION BY {first.partition_method} ({first.partition_expression}) (\n  "
        + ",\n  ".join(parts)
        + "\n)"
    )


def _build_create_table(
    table: TableInfo,
    columns: list[ColumnInfo],
    indexes: list[IndexInfo],
    partitions: list[PartitionInfo],
    options: TransformOptions,
    notes: list[str],
    apply_rules: bool,
) -> str:
    col_lines = [
        _convert_column(col, options, notes, apply_rules)
        for col in columns
    ]

    pk = _build_primary_key(indexes)
    if pk:
        col_lines.append(pk)

    table_collation = table.table_collation
    if apply_rules:
        table_collation = _apply_collation(table_collation, options, notes)

    engine = "InnoDB" if apply_rules else (table.engine or "InnoDB")
    if apply_rules and table.engine and table.engine.upper() != "INNODB":
        notes.append(
            f"Engine normalized for {table.table_schema}.{table.table_name}: {table.engine} -> InnoDB"
        )

    parts = _build_partitions(partitions)

    ddl = [
        f"CREATE TABLE {_quote_identifier(table.table_schema)}.{_quote_identifier(table.table_name)} (",
        "  " + ",\n  ".join(col_lines),
        ")",
        f"ENGINE={engine}",
    ]

    if table_collation:
        ddl.append(f"DEFAULT COLLATE={table_collation}")

    if parts:
        ddl.append(parts)

    ddl_sql = "\n".join(ddl) + ";"

    if apply_rules:
        if any("auto_increment" in (c.extra or "").lower() for c in columns):
            ddl_sql += "\n/* TiShift: AUTO_INCREMENT values will be unique but not sequential in TiDB */"

    return ddl_sql


def _build_views(views: list[ViewInfo], notes: list[str]) -> list[str]:
    stmts: list[str] = []
    for view in views:
        if not view.view_definition:
            notes.append(f"View {view.table_schema}.{view.table_name} has no definition in metadata")
            continue
        stmt = (
            f"CREATE OR REPLACE VIEW {_quote_identifier(view.table_schema)}." \
            f"{_quote_identifier(view.table_name)} AS {view.view_definition};"
        )
        stmts.append(stmt)
    return stmts


def transform_schema(
    inventory: SchemaInventory,
    options: TransformOptions | None = None,
) -> SchemaConversionResult:
    """Transform a schema inventory into TiDB-compatible DDL."""
    if options is None:
        options = TransformOptions()

    notes: list[str] = []

    tables_by_name = _group_by_table(inventory.tables, key_attr="table_name")
    cols_by_table = _group_by_table(inventory.columns, key_attr="table_name")
    idx_by_table = _group_by_table(inventory.indexes, key_attr="table_name")
    fk_by_table = _group_by_table(inventory.foreign_keys, key_attr="table_name")
    part_by_table = _group_by_table(inventory.partitions, key_attr="table_name")

    create_tables: list[str] = []
    original_tables: list[str] = []

    for table in inventory.tables:
        columns = cols_by_table.get(table.table_name, [])
        indexes = idx_by_table.get(table.table_name, [])
        partitions = part_by_table.get(table.table_name, [])

        original_tables.append(
            _build_create_table(table, columns, indexes, partitions, options, notes, apply_rules=False)
        )
        create_tables.append(
            _build_create_table(table, columns, indexes, partitions, options, notes, apply_rules=True)
        )

    index_sql, _ = _build_indexes(inventory.indexes, options, notes)
    fk_sql = _build_foreign_keys(inventory.foreign_keys)
    view_sql = _build_views(inventory.views, notes)

    result = SchemaConversionResult(
        create_tables_sql="\n\n".join(create_tables) + ("\n" if create_tables else ""),
        create_indexes_sql="\n".join(index_sql) + ("\n" if index_sql else ""),
        create_views_sql="\n".join(view_sql) + ("\n" if view_sql else ""),
        foreign_keys_sql="\n".join(fk_sql) + ("\n" if fk_sql else ""),
        conversion_notes=notes,
        original_schema_sql="\n\n".join(original_tables) + ("\n" if original_tables else ""),
    )

    return result


def generate_schema_diff(original_sql: str, converted_sql: str) -> str:
    """Generate a unified diff between original and converted DDL."""
    original_lines = original_sql.splitlines()
    converted_lines = converted_sql.splitlines()
    diff = difflib.unified_diff(
        original_lines,
        converted_lines,
        fromfile="aurora.sql",
        tofile="tidb.sql",
        lineterm="",
    )
    return "\n".join(diff) + "\n"
