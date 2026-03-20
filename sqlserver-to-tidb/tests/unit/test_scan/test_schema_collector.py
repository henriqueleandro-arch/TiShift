"""Tests for schema collector — mocked pymssql cursor → dataclass mapping."""

from __future__ import annotations

from tishift_mssql.scan.collectors.schema import collect_schema


class TestCollectSchema:
    def test_maps_tables(self, mock_pymssql_connection) -> None:
        inventory = collect_schema(mock_pymssql_connection, database=None)
        assert len(inventory.tables) == 1
        assert inventory.tables[0].table_name == "users"
        assert inventory.tables[0].schema_name == "dbo"
        assert inventory.tables[0].row_count == 10

    def test_maps_columns(self, mock_pymssql_connection) -> None:
        inventory = collect_schema(mock_pymssql_connection, database=None)
        assert len(inventory.columns) == 1
        col = inventory.columns[0]
        assert col.column_name == "id"
        assert col.data_type == "int"
        assert col.is_identity is True

    def test_maps_indexes(self, mock_pymssql_connection) -> None:
        inventory = collect_schema(mock_pymssql_connection, database=None)
        assert len(inventory.indexes) == 1
        idx = inventory.indexes[0]
        assert idx.index_name == "PK_users"
        assert idx.is_primary_key is True
        assert idx.index_type == "CLUSTERED"
        assert "id" in idx.columns

    def test_handles_empty_results(self, mock_pymssql_connection) -> None:
        inventory = collect_schema(mock_pymssql_connection, database=None)
        # Foreign keys, routines, triggers, views, assemblies, linked servers
        # are all empty in the mock script
        assert len(inventory.foreign_keys) == 0
        assert len(inventory.routines) == 0
        assert len(inventory.triggers) == 0
        assert len(inventory.views) == 0
        assert len(inventory.assemblies) == 0
        assert len(inventory.linked_servers) == 0

    def test_partition_functions(self, mock_pymssql_connection) -> None:
        inventory = collect_schema(mock_pymssql_connection, database=None)
        assert "pf_orders" in inventory.partition_functions

    def test_schemas_collected(self, mock_pymssql_connection) -> None:
        inventory = collect_schema(mock_pymssql_connection, database=None)
        assert "dbo" in inventory.schemas
