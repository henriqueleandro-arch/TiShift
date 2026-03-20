"""Tests for scan collectors using mock database connections."""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from tishift.core.scan.collectors.aurora import collect_aurora_metadata
from tishift.core.scan.collectors.data_profile import collect_data_profile
from tishift.core.scan.collectors.queries import collect_query_patterns
from tishift.core.scan.collectors.schema import collect_schema


class TestSchemaCollector:
    def test_returns_schema_inventory(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.return_value = []
        result = collect_schema(mock_connection)
        assert result.tables == []
        assert result.columns == []
        assert result.indexes == []

    def test_collects_tables(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.side_effect = [
            # tables
            [{"table_schema": "db", "table_name": "t1", "engine": "InnoDB",
              "row_format": "Dynamic", "table_rows": 100, "data_length": 16384,
              "index_length": 8192, "auto_increment": 101,
              "table_collation": "utf8mb4_general_ci", "create_options": ""}],
            # columns, indexes, fks, routines, triggers, views, events, partitions, charset
            [], [], [], [], [], [], [], [], [],
        ]
        result = collect_schema(mock_connection)
        assert len(result.tables) == 1
        assert result.tables[0].table_name == "t1"
        assert result.tables[0].engine == "InnoDB"

    def test_filters_by_database(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.return_value = []
        collect_schema(mock_connection, database="mydb")
        # Verify parameterized query was used (params tuple with database name).
        first_call = mock_cursor.execute.call_args_list[0]
        assert first_call[0][1] == ("mydb",)


class TestDataProfileCollector:
    def test_returns_profile(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.side_effect = [
            [{"table_schema": "db", "table_name": "t1", "table_rows": 50,
              "data_mb": 1.5, "index_mb": 0.3, "total_mb": 1.8}],
            [],  # blob columns
        ]
        result = collect_data_profile(mock_connection)
        assert len(result.table_sizes) == 1
        assert result.total_data_mb == 1.5
        assert result.total_rows == 50

    def test_detects_blob_columns(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.side_effect = [
            [],  # table sizes
            [{"table_schema": "db", "table_name": "t1",
              "column_name": "data", "data_type": "longblob"}],
        ]
        result = collect_data_profile(mock_connection)
        assert len(result.blob_columns) == 1
        assert result.blob_columns[0].data_type == "longblob"


class TestAuroraCollector:
    def test_collects_metadata(self, mock_connection, mock_cursor):
        # Each _get_var call does cursor.execute + fetchone.
        mock_cursor.fetchone.side_effect = [
            {"@@aurora_version": "3.07.1"},
            {"@@version": "8.0.36"},
            {"@@version_comment": "Aurora MySQL"},
            {"@@binlog_format": "ROW"},
            {"@@binlog_row_image": "FULL"},
            {"@@character_set_server": "utf8mb4"},
            {"@@collation_server": "utf8mb4_0900_ai_ci"},
            {"@@transaction_isolation": "REPEATABLE-READ"},
            {"@@sql_mode": "STRICT_TRANS_TABLES"},
            {"@@max_connections": "1000"},
            {"@@innodb_buffer_pool_size": "134217728"},
            {"@@lower_case_table_names": "0"},
            {"@@explicit_defaults_for_timestamp": "ON"},
        ]
        result = collect_aurora_metadata(mock_connection)
        assert result.aurora_version == "3.07.1"
        assert result.mysql_version == "8.0.36"
        assert result.binlog_format == "ROW"

    def test_handles_non_aurora(self, mock_connection, mock_cursor):
        import pymysql
        # aurora_version fails, rest succeed.
        mock_cursor.execute.side_effect = [
            pymysql.Error("Unknown system variable"),
        ] + [None] * 12
        mock_cursor.fetchone.side_effect = [
            {"@@version": "8.0.36"},
            {"@@version_comment": "MySQL Community"},
            {"@@binlog_format": "ROW"},
            {"@@binlog_row_image": "FULL"},
            {"@@character_set_server": "utf8mb4"},
            {"@@collation_server": "utf8mb4_general_ci"},
            {"@@transaction_isolation": "REPEATABLE-READ"},
            {"@@sql_mode": "STRICT_TRANS_TABLES"},
            {"@@max_connections": "151"},
            {"@@innodb_buffer_pool_size": "134217728"},
            {"@@lower_case_table_names": "0"},
            {"@@explicit_defaults_for_timestamp": "ON"},
        ]
        result = collect_aurora_metadata(mock_connection)
        assert result.aurora_version is None
        assert result.mysql_version == "8.0.36"


class TestQueryPatternCollector:
    def test_returns_empty_on_access_denied(self, mock_connection, mock_cursor):
        import pymysql
        mock_cursor.execute.side_effect = pymysql.Error("Access denied")
        result = collect_query_patterns(mock_connection)
        assert result.total_digests_analyzed == 0
        assert result.issues == []

    def test_detects_xa_pattern(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.return_value = [
            {"digest_text": "XA START ?", "count_star": 10,
             "sum_timer_wait": 100, "sum_rows_affected": 0,
             "sum_rows_sent": 0, "sum_rows_examined": 0},
        ]
        result = collect_query_patterns(mock_connection)
        assert len(result.issues) == 1
        assert result.issues[0].construct == "XA_TRANSACTION"

    def test_detects_get_lock(self, mock_connection, mock_cursor):
        mock_cursor.fetchall.return_value = [
            {"digest_text": "SELECT GET_LOCK(?, ?)", "count_star": 5,
             "sum_timer_wait": 50, "sum_rows_affected": 0,
             "sum_rows_sent": 5, "sum_rows_examined": 5},
        ]
        result = collect_query_patterns(mock_connection)
        assert any(i.construct == "GET_LOCK" for i in result.issues)
