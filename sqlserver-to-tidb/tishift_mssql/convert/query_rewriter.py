"""Query rewrite placeholder."""

from __future__ import annotations

import sqlglot


def rewrite_tsql_to_mysql(sql_text: str) -> str:
    """Transpile T-SQL snippet to MySQL syntax."""
    return ";\n".join(sqlglot.transpile(sql_text, read="tsql", write="mysql"))
