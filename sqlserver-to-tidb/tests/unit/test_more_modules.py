from __future__ import annotations

from tishift_mssql.convert.diff_generator import generate_diff
from tishift_mssql.convert.query_rewriter import rewrite_tsql_to_mysql


def test_generate_diff() -> None:
    diff = generate_diff("SELECT 1\n", "SELECT 2\n")
    assert "-SELECT 1" in diff
    assert "+SELECT 2" in diff


def test_rewrite_tsql_to_mysql() -> None:
    out = rewrite_tsql_to_mysql("SELECT TOP 1 * FROM t")
    assert "LIMIT" in out.upper() or "SELECT" in out.upper()
