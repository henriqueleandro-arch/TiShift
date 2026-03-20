"""Shared test fixtures for TiShift SQL Server scanner."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tishift_mssql.models import (
    AgentJobInfo,
    AssemblyInfo,
    ColumnInfo,
    DataProfile,
    FeatureScanResult,
    FeatureUsage,
    IndexInfo,
    LinkedServerInfo,
    RoutineInfo,
    SQLServerMetadata,
    SchemaInventory,
    TableInfo,
    TableSize,
    TriggerInfo,
    ViewInfo,
)


@pytest.fixture
def sample_inventory() -> SchemaInventory:
    """Sample schema inventory matching the spec's test database."""
    return SchemaInventory(
        tables=[
            TableInfo("dbo", "customers", 100, 12.0, 10.0, False, False, False),
            TableInfo("dbo", "orders", 200, 24.0, 20.0, False, False, False),
            TableInfo("dbo", "audit_log", 50, 2.0, 1.5, False, False, False),
        ],
        columns=[
            ColumnInfo("dbo", "customers", "id", 1, "bigint", 8, 19, 0, False, True, False, None, None, None),
            ColumnInfo("dbo", "customers", "name", 2, "nvarchar", 510, None, None, False, False, False, "SQL_Latin1_General_CP1_CI_AS", None, None),
            ColumnInfo("dbo", "customers", "email", 3, "varchar", 255, None, None, True, False, False, None, None, None),
            ColumnInfo("dbo", "customers", "balance", 4, "money", 8, 19, 4, False, False, False, None, None, None),
            ColumnInfo("dbo", "customers", "guid", 5, "uniqueidentifier", 16, None, None, True, False, False, None, None, "(newid())"),
            ColumnInfo("dbo", "customers", "created_at", 6, "datetime2", 8, 27, 3, True, False, False, None, None, "(sysdatetime())"),
            ColumnInfo("dbo", "customers", "is_active", 7, "bit", 1, None, None, True, False, False, None, None, "((1))"),
            ColumnInfo("dbo", "orders", "id", 1, "bigint", 8, 19, 0, False, True, False, None, None, None),
            ColumnInfo("dbo", "orders", "total", 2, "decimal", 9, 10, 2, True, False, False, None, None, None),
            ColumnInfo("dbo", "orders", "status", 3, "varchar", 20, None, None, True, False, False, None, None, None),
            # XML column to trigger blocker
            ColumnInfo("dbo", "audit_log", "details", 2, "xml", -1, None, None, True, False, False, None, None, None),
        ],
        indexes=[
            IndexInfo("dbo", "customers", "PK_customers", "CLUSTERED", True, True, "id", "", None),
            IndexInfo("dbo", "customers", "ix_email", "NONCLUSTERED", True, False, "email", "", None),
        ],
        foreign_keys=[],
        routines=[
            RoutineInfo(
                "dbo", "get_customer_summary", "SQL_STORED_PROCEDURE",
                "CREATE PROCEDURE dbo.get_customer_summary\n    @cust_id BIGINT\nAS\nBEGIN\n    SET NOCOUNT ON;\n    SELECT * FROM customers WHERE id = @cust_id;\nEND;",
                False, None,
            ),
            RoutineInfo(
                "dbo", "upsert_customer", "SQL_STORED_PROCEDURE",
                "CREATE PROCEDURE dbo.upsert_customer\nAS\nBEGIN\n    MERGE INTO customers AS target\n    USING source ON target.email = source.email\n    WHEN MATCHED THEN UPDATE SET name = source.name\n    WHEN NOT MATCHED THEN INSERT (name, email) VALUES (source.name, source.email);\nEND;",
                False, None,
            ),
        ],
        triggers=[
            TriggerInfo("dbo", "trg_orders_audit", "orders", False, False, "CREATE TRIGGER dbo.trg_orders_audit ON dbo.orders AFTER INSERT AS BEGIN SELECT * FROM inserted FOR XML PATH(''); END;"),
        ],
        views=[
            ViewInfo("dbo", "customer_order_summary", "CREATE VIEW dbo.customer_order_summary AS SELECT id FROM customers FOR XML PATH('');", False, False),
        ],
        assemblies=[],
        linked_servers=[],
        agent_jobs=[],
        schemas=["dbo"],
    )


@pytest.fixture
def sample_inventory_complex(sample_inventory: SchemaInventory) -> SchemaInventory:
    """Inventory with CLR, linked servers, agent jobs, memory-optimized and temporal tables."""
    sample_inventory.tables.append(TableInfo("dbo", "in_mem_table", 10, 1.0, 0.5, True, False, False))
    sample_inventory.tables.append(TableInfo("dbo", "temporal_table", 10, 1.0, 0.5, False, True, False))
    sample_inventory.columns.append(
        ColumnInfo("dbo", "customers", "geo", 8, "geography", -1, None, None, True, False, False, None, None, None)
    )
    sample_inventory.columns.append(
        ColumnInfo("dbo", "customers", "variant_col", 9, "sql_variant", -1, None, None, True, False, False, None, None, None)
    )
    sample_inventory.columns.append(
        ColumnInfo("dbo", "customers", "hierarchy", 10, "hierarchyid", 892, None, None, True, False, False, None, None, None)
    )
    sample_inventory.assemblies = [AssemblyInfo("StringUtils", "SAFE", "StringUtils, Version=1.0")]
    sample_inventory.linked_servers = [LinkedServerInfo("REMOTE_SRV", "SQL Server", "SQLOLEDB", "remote.example.com")]
    sample_inventory.agent_jobs = [AgentJobInfo("daily_cleanup", True, "Daily cleanup job")]
    sample_inventory.indexes.append(
        IndexInfo("dbo", "orders", "ix_status_filtered", "NONCLUSTERED", False, False, "status", "", "status = 'active'")
    )
    sample_inventory.indexes.append(
        IndexInfo("dbo", "orders", "ix_columnstore", "CLUSTERED COLUMNSTORE", False, False, "", "", None)
    )
    sample_inventory.schemas = ["dbo", "sales", "hr"]
    return sample_inventory


@pytest.fixture
def sample_metadata() -> SQLServerMetadata:
    return SQLServerMetadata(
        version="Microsoft SQL Server 2022 (RTM)",
        edition="Enterprise Edition",
        product_version="16.0.4135.4",
        engine_edition=3,
        cpu_count=8,
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        db_size_mb=152_700.0,
        cdc_enabled=True,
        configuration={"clr enabled": "1", "max degree of parallelism": "4"},
        has_ssis=False,
        auth_mode="sql",
    )


@pytest.fixture
def sample_metadata_old_no_cdc() -> SQLServerMetadata:
    """SQL Server 2014 with no CDC and Windows auth."""
    return SQLServerMetadata(
        version="Microsoft SQL Server 2014 (SP3)",
        edition="Standard Edition",
        product_version="12.0.6024.0",
        engine_edition=2,
        cpu_count=4,
        db_collation="Latin1_General_100_CI_AS",
        db_size_mb=50_000.0,
        cdc_enabled=False,
        has_ssis=True,
        auth_mode="windows",
    )


@pytest.fixture
def sample_data_profile() -> DataProfile:
    return DataProfile(
        table_sizes=[
            TableSize("dbo", "customers", 100, 12.0, 10.0, 2.0),
            TableSize("dbo", "orders", 200, 24.0, 20.0, 4.0),
        ],
        total_rows=300,
        total_data_mb=30.0,
        total_index_mb=6.0,
    )


@pytest.fixture
def large_data_profile() -> DataProfile:
    """Data profile exceeding 1 TB with a single 100GB+ table."""
    return DataProfile(
        table_sizes=[
            TableSize("dbo", "big_table", 500_000_000, 120_000.0, 110_000.0, 10_000.0),
            TableSize("dbo", "huge_table", 2_000_000_000, 1_100_000.0, 1_000_000.0, 100_000.0),
        ],
        total_rows=2_500_000_000,
        total_data_mb=1_110_000.0,
        total_index_mb=110_000.0,
    )


@pytest.fixture
def sample_feature_scan() -> FeatureScanResult:
    return FeatureScanResult(
        usages=[
            FeatureUsage("merge", "routine", "dbo.upsert_customer", "MERGE INTO customers"),
            FeatureUsage("cursor", "routine", "dbo.sp_complex", "DECLARE c CURSOR"),
            FeatureUsage("for_xml", "trigger", "dbo.trg_orders_audit", "FOR XML PATH"),
            FeatureUsage("nolock", "routine", "dbo.sp_read", "WITH (NOLOCK)"),
        ]
    )


@pytest.fixture
def empty_feature_scan() -> FeatureScanResult:
    return FeatureScanResult()


# ---------------------------------------------------------------------------
# Mock pymssql connection
# ---------------------------------------------------------------------------


class _MockCursor:
    """Cursor mock that plays back scripted responses in order."""

    def __init__(self, script: list[object]) -> None:
        self.script = list(script)
        self.idx = 0
        self.last_query: str = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query: str):
        self.last_query = query

    def fetchall(self):
        if self.idx >= len(self.script):
            return []
        payload = self.script[self.idx]
        self.idx += 1
        return payload if isinstance(payload, list) else []

    def fetchone(self):
        if self.idx >= len(self.script):
            return {}
        payload = self.script[self.idx]
        self.idx += 1
        return payload if isinstance(payload, dict) else {}


class _MockConnection:
    def __init__(self, script: list[object]) -> None:
        self._cursor = _MockCursor(script)

    def cursor(self):
        return self._cursor

    def close(self):
        pass


@pytest.fixture
def mock_pymssql_connection() -> Iterator[_MockConnection]:
    """Mock connection with scripted responses matching schema collector query order."""
    script: list[object] = [
        # 1. tables
        [{"schema_name": "dbo", "table_name": "users", "row_count": 10, "total_mb": 1.0, "used_mb": 0.9,
          "is_memory_optimized": 0, "is_temporal": 0, "is_heap": 1}],
        # 2. columns
        [{"schema_name": "dbo", "table_name": "users", "column_name": "id", "column_id": 1,
          "data_type": "int", "max_length": 4, "precision": 10, "scale": 0,
          "is_nullable": 0, "is_identity": 1, "is_computed": 0, "is_filestream": 0,
          "collation_name": None, "computed_definition": None, "default_definition": None}],
        # 3. indexes
        [{"schema_name": "dbo", "table_name": "users", "index_name": "PK_users",
          "index_type": "CLUSTERED", "is_unique": 1, "is_primary_key": 1,
          "filter_definition": None, "column_name": "id", "is_included_column": 0, "key_ordinal": 1}],
        # 4. foreign keys
        [],
        # 5. routines
        [],
        # 6. triggers
        [],
        # 7. views
        [],
        # 8. assemblies
        [],
        # 9. linked servers
        [],
        # 10. agent jobs
        [],
        # 11. partition functions
        [{"name": "pf_orders"}],
        # 12. schemas
        [{"name": "dbo"}],
    ]
    yield _MockConnection(script)
