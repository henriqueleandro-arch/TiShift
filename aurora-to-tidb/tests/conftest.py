"""Shared fixtures for TiShift tests.

Provides mock PyMySQL cursors and connections, plus sample data matching
the spec's test Aurora schema.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tishift.config import SourceConfig
from tishift.models import (
    AuroraMetadata,
    BlobColumn,
    CharsetUsage,
    ColumnInfo,
    DataProfile,
    EventInfo,
    ForeignKeyInfo,
    IndexInfo,
    PartitionInfo,
    RoutineInfo,
    SchemaInventory,
    TableInfo,
    TableSize,
    TriggerInfo,
    ViewInfo,
)


@pytest.fixture
def source_config() -> SourceConfig:
    return SourceConfig(
        host="aurora-test.example.com",
        port=3306,
        user="admin",
        password="testpass",
        database="tishift_test",
    )


@pytest.fixture
def mock_cursor():
    """A MagicMock that behaves like a PyMySQL DictCursor."""
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    return cursor


@pytest.fixture
def mock_connection(mock_cursor):
    """A MagicMock that behaves like a PyMySQL Connection."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


@pytest.fixture
def sample_inventory() -> SchemaInventory:
    """Sample schema inventory matching the spec's test database."""
    return SchemaInventory(
        tables=[
            TableInfo(
                table_schema="tishift_test", table_name="customers",
                engine="InnoDB", row_format="Dynamic", table_rows=3,
                data_length=16384, index_length=16384,
                auto_increment=4, table_collation="utf8mb4_0900_ai_ci",
                create_options="",
            ),
            TableInfo(
                table_schema="tishift_test", table_name="orders",
                engine="InnoDB", row_format="Dynamic", table_rows=3,
                data_length=16384, index_length=32768,
                auto_increment=4, table_collation="utf8mb4_0900_ai_ci",
                create_options="",
            ),
            TableInfo(
                table_schema="tishift_test", table_name="audit_log",
                engine="InnoDB", row_format="Dynamic", table_rows=0,
                data_length=16384, index_length=0,
                auto_increment=1, table_collation="utf8mb4_0900_ai_ci",
                create_options="",
            ),
        ],
        columns=[
            ColumnInfo("tishift_test", "customers", "id", 1, None, "NO", "bigint", "bigint", None, None, "PRI", "auto_increment", None),
            ColumnInfo("tishift_test", "customers", "name", 2, None, "NO", "varchar", "varchar(255)", "utf8mb4", "utf8mb4_0900_ai_ci", "", "", None),
            ColumnInfo("tishift_test", "customers", "email", 3, None, "YES", "varchar", "varchar(255)", "utf8mb4", "utf8mb4_0900_ai_ci", "UNI", "", None),
            ColumnInfo("tishift_test", "customers", "created_at", 4, "CURRENT_TIMESTAMP", "YES", "timestamp", "timestamp", None, None, "", "DEFAULT_GENERATED", None),
            ColumnInfo("tishift_test", "orders", "id", 1, None, "NO", "bigint", "bigint", None, None, "PRI", "auto_increment", None),
            ColumnInfo("tishift_test", "orders", "customer_id", 2, None, "YES", "bigint", "bigint", None, None, "MUL", "", None),
            ColumnInfo("tishift_test", "orders", "total", 3, None, "YES", "decimal", "decimal(10,2)", None, None, "", "", None),
            ColumnInfo("tishift_test", "orders", "status", 4, None, "YES", "enum", "enum('pending','shipped','delivered')", "utf8mb4", "utf8mb4_0900_ai_ci", "", "", None),
            ColumnInfo("tishift_test", "orders", "metadata", 5, None, "YES", "json", "json", None, None, "", "", None),
        ],
        indexes=[
            IndexInfo("tishift_test", "customers", "PRIMARY", 0, "BTREE", "id"),
            IndexInfo("tishift_test", "customers", "idx_email", 0, "BTREE", "email"),
            IndexInfo("tishift_test", "orders", "PRIMARY", 0, "BTREE", "id"),
            IndexInfo("tishift_test", "orders", "customer_id", 1, "BTREE", "customer_id"),
        ],
        foreign_keys=[
            ForeignKeyInfo(
                "tishift_test", "orders", "orders_ibfk_1",
                "tishift_test", "customers", "customer_id", "id",
            ),
        ],
        routines=[
            RoutineInfo(
                routine_schema="tishift_test",
                routine_name="get_customer_orders",
                routine_type="PROCEDURE",
                data_type=None,
                routine_body="SQL",
                routine_definition=(
                    "BEGIN\n"
                    "  DECLARE total_orders INT;\n"
                    "  SELECT COUNT(*) INTO total_orders FROM orders WHERE customer_id = cust_id;\n"
                    "  SELECT c.name, c.email, total_orders as order_count\n"
                    "  FROM customers c\n"
                    "  LEFT JOIN orders o ON c.id = o.customer_id\n"
                    "  WHERE c.id = cust_id\n"
                    "  GROUP BY c.id;\n"
                    "END"
                ),
                is_deterministic="NO",
                security_type="DEFINER",
                definer="admin@%",
            ),
        ],
        triggers=[
            TriggerInfo(
                trigger_schema="tishift_test",
                trigger_name="after_order_insert",
                event_manipulation="INSERT",
                event_object_table="orders",
                action_statement=(
                    "BEGIN\n"
                    "  INSERT INTO audit_log (table_name, action, record_id, created_at)\n"
                    "  VALUES ('orders', 'INSERT', NEW.id, NOW());\n"
                    "END"
                ),
                action_timing="AFTER",
            ),
        ],
        views=[],
        events=[],
        partitions=[],
        charset_usage=[
            CharsetUsage("utf8mb4", "utf8mb4_0900_ai_ci", 5),
        ],
    )


@pytest.fixture
def sample_data_profile() -> DataProfile:
    return DataProfile(
        table_sizes=[
            TableSize("tishift_test", "customers", 3, 0.02, 0.02, 0.03),
            TableSize("tishift_test", "orders", 3, 0.02, 0.03, 0.05),
            TableSize("tishift_test", "audit_log", 0, 0.02, 0.0, 0.02),
        ],
        blob_columns=[],
        total_data_mb=0.06,
        total_index_mb=0.05,
        total_rows=6,
    )


@pytest.fixture
def sample_aurora_metadata() -> AuroraMetadata:
    return AuroraMetadata(
        aurora_version="3.07.1",
        mysql_version="8.0.36",
        version_comment="Aurora MySQL",
        binlog_format="ROW",
        binlog_row_image="FULL",
        character_set_server="utf8mb4",
        collation_server="utf8mb4_0900_ai_ci",
        transaction_isolation="REPEATABLE-READ",
        sql_mode="ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE",
        max_connections=1000,
        innodb_buffer_pool_size=134217728,
        lower_case_table_names=0,
        explicit_defaults_for_timestamp="ON",
    )
