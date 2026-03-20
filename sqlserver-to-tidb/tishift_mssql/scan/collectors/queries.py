"""Query pattern collector with sqlglot transpile checks."""

from __future__ import annotations

import pymssql
import sqlglot

from tishift_mssql.models import QueryIssue, QueryPatterns, Severity
from tishift_mssql.rules.tsql_patterns import TSQL_PATTERNS


_QUERY_SQL = """
SELECT TOP 200
    st.text AS query_text,
    qs.execution_count
FROM sys.dm_exec_query_stats qs
CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st
ORDER BY qs.execution_count DESC
"""


def collect_query_patterns(conn: pymssql.Connection) -> QueryPatterns:
    """Collect top executed queries and identify non-portable patterns."""
    patterns = QueryPatterns()

    with conn.cursor() as cur:
        cur.execute(_QUERY_SQL)
        rows = cur.fetchall()

    for row in rows:
        query_text = (row.get("query_text") or "").strip()
        if not query_text:
            continue

        patterns.total_queries_analyzed += 1
        transpile_ok = True
        try:
            sqlglot.transpile(query_text, read="tsql", write="mysql")
        except Exception:
            transpile_ok = False
            patterns.transpile_failures += 1

        for name, regex in TSQL_PATTERNS.items():
            if regex.search(query_text):
                patterns.issues.append(
                    QueryIssue(
                        query_snippet=query_text[:240],
                        construct=name,
                        severity=Severity.WARNING if transpile_ok else Severity.BLOCKER,
                        message=f"Detected {name} construct in frequently executed SQL",
                        transpile_ok=transpile_ok,
                    )
                )

    return patterns
