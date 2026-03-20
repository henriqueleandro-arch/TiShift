"""Tests for table checker."""

from __future__ import annotations

from unittest.mock import MagicMock

from tishift.core.check.table_checker import compare_row_counts, compare_table_structures


def _mock_conn(rows):
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = rows
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    return conn


def test_compare_row_counts():
    src = _mock_conn([
        {"table_name": "t1", "table_rows": 10},
        {"table_name": "t2", "table_rows": 5},
    ])
    tgt = _mock_conn([
        {"table_name": "t1", "table_rows": 10},
        {"table_name": "t2", "table_rows": 6},
    ])
    results = compare_row_counts(src, tgt, "test")
    assert len(results) == 2
    assert any(r.table_name == "t2" and not r.row_count_match for r in results)


def test_compare_table_structures():
    src = _mock_conn([
        {"table_name": "t1", "column_name": "id", "column_type": "int"},
    ])
    tgt = _mock_conn([
        {"table_name": "t1", "column_name": "id", "column_type": "bigint"},
    ])
    results = compare_table_structures(src, tgt, "test")
    assert len(results) == 1
    assert results[0].match is False
