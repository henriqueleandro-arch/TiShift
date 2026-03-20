"""Schema conversion helpers for SQL Server -> TiDB DDL."""

from __future__ import annotations

from collections import defaultdict

from tishift_mssql.rules.type_mapping import TYPE_MAPPING


def _ident(name: str) -> str:
    return f"`{name.replace('`', '``')}`"


def map_table_name(schema: str, table: str, schema_mapping: str) -> tuple[str | None, str]:
    """Map SQL Server schema.table into target logical table location."""
    schema_lower = schema.lower()
    if schema_mapping == "flatten":
        return None, table
    if schema_mapping == "prefix":
        if schema_lower == "dbo":
            return None, table
        return None, f"{schema}_{table}"
    if schema_mapping == "database":
        return schema, table
    raise ValueError(f"Unsupported schema mapping mode: {schema_mapping}")


def _map_type(column: dict[str, object]) -> str:
    source_type = str(column.get("data_type") or "").lower()
    mapped = TYPE_MAPPING.get(source_type, source_type.upper() or "TEXT")

    if source_type in {"varchar", "nvarchar", "char", "nchar", "binary", "varbinary"}:
        max_length = column.get("max_length")
        if isinstance(max_length, int) and max_length > 0:
            return f"{mapped}({max_length})"
        if isinstance(max_length, int) and max_length < 0:
            if source_type in {"varbinary"}:
                return "LONGBLOB"
            return "LONGTEXT"

    if source_type in {"decimal", "numeric"}:
        precision = int(column.get("precision") or 18)
        scale = int(column.get("scale") or 0)
        return f"DECIMAL({precision},{scale})"

    if source_type == "datetime2":
        precision = int(column.get("scale") or 6)
        precision = min(max(precision, 0), 6)
        return f"DATETIME({precision})"

    return mapped


def generate_schema_ddl(scan_report: dict[str, object], schema_mapping: str) -> tuple[list[str], list[str]]:
    """Generate CREATE TABLE DDL from scanner inventory model."""
    inventory = scan_report.get("schema_inventory")
    if not isinstance(inventory, dict):
        return [], ["Invalid schema_inventory payload"]

    tables = inventory.get("tables") or []
    columns = inventory.get("columns") or []
    indexes = inventory.get("indexes") or []

    if not isinstance(tables, list) or not isinstance(columns, list) or not isinstance(indexes, list):
        return [], ["Invalid schema inventory arrays"]

    columns_by_table: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for col in columns:
        if isinstance(col, dict):
            key = (str(col.get("schema_name") or "dbo"), str(col.get("table_name") or ""))
            columns_by_table[key].append(col)

    for col_list in columns_by_table.values():
        col_list.sort(key=lambda c: int(c.get("ordinal_position") or 0))

    primary_keys: dict[tuple[str, str], list[str]] = defaultdict(list)
    for idx in indexes:
        if not isinstance(idx, dict) or not idx.get("is_primary_key"):
            continue
        schema_name = str(idx.get("schema_name") or "dbo")
        table_name = str(idx.get("table_name") or "")
        columns_csv = str(idx.get("columns") or "")
        pk_cols = [c.strip() for c in columns_csv.split(",") if c.strip()]
        primary_keys[(schema_name, table_name)].extend(pk_cols)

    ddl_statements: list[str] = []
    warnings: list[str] = []
    seen_targets: dict[tuple[str | None, str], tuple[str, str]] = {}

    for table in tables:
        if not isinstance(table, dict):
            continue
        schema_name = str(table.get("schema_name") or "dbo")
        table_name = str(table.get("table_name") or "")
        target_db, target_table = map_table_name(schema_name, table_name, schema_mapping)

        target_key = (target_db, target_table)
        if target_key in seen_targets and seen_targets[target_key] != (schema_name, table_name):
            warnings.append(
                f"Name collision: {schema_name}.{table_name} and {seen_targets[target_key][0]}.{seen_targets[target_key][1]} map to {target_table}"
            )
        seen_targets[target_key] = (schema_name, table_name)

        table_cols = columns_by_table.get((schema_name, table_name), [])
        if not table_cols:
            warnings.append(f"No columns found for {schema_name}.{table_name}")
            continue

        col_lines: list[str] = []
        for col in table_cols:
            col_name = str(col.get("column_name") or "")
            col_type = _map_type(col)
            nullable = bool(col.get("is_nullable"))
            line = f"  {_ident(col_name)} {col_type}"
            if not nullable:
                line += " NOT NULL"
            default_definition = col.get("default_definition")
            if isinstance(default_definition, str) and default_definition.strip():
                line += f" /* default {default_definition.strip()} */"
            if bool(col.get("is_identity")):
                line += " AUTO_INCREMENT"
            if bool(col.get("is_computed")):
                line += " /* computed column: manual review */"
            col_lines.append(line)

        pk = primary_keys.get((schema_name, table_name), [])
        if pk:
            pk_expr = ", ".join(_ident(name) for name in pk)
            col_lines.append(f"  PRIMARY KEY ({pk_expr})")

        full_name = _ident(target_table)
        if target_db:
            full_name = f"{_ident(target_db)}.{full_name}"

        ddl = "CREATE TABLE IF NOT EXISTS " + full_name + " (\n" + ",\n".join(col_lines) + "\n) ENGINE=InnoDB;"
        ddl_statements.append(ddl)

    return ddl_statements, warnings
