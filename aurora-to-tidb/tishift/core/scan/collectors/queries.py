"""Query pattern collector.

Reads performance_schema digests and uses sqlglot to detect
TiDB-incompatible SQL constructs.

This collector is optional (only runs with --include-query-log).
Handles performance_schema access failures gracefully.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pymysql

from tishift.models import QueryDigest, QueryIssue, QueryPatterns, Severity

logger = logging.getLogger(__name__)

# Functions and constructs that are incompatible or problematic in TiDB.
_INCOMPATIBLE_PATTERNS: list[tuple[str, str, Severity, str, str]] = [
    # (regex_pattern, construct_name, severity, message, suggestion)
    (
        r"\bExtractValue\s*\(", "XML_EXTRACT",
        Severity.WARNING,
        "ExtractValue() is not supported in TiDB",
        "Use JSON functions (JSON_EXTRACT) instead",
    ),
    (
        r"\bUpdateXML\s*\(", "XML_UPDATE",
        Severity.WARNING,
        "UpdateXML() is not supported in TiDB",
        "Use JSON functions (JSON_SET / JSON_REPLACE) instead",
    ),
    (
        r"\bST_\w+\s*\(", "SPATIAL",
        Severity.WARNING,
        "Spatial functions are not supported in TiDB",
        "Consider using external GIS service or encoding coordinates as numeric columns",
    ),
    (
        r"\bGET_LOCK\s*\(", "GET_LOCK",
        Severity.WARNING,
        "GET_LOCK() has limited support in TiDB",
        "Use Redis or application-level distributed locking instead",
    ),
    (
        r"\bRELEASE_LOCK\s*\(", "RELEASE_LOCK",
        Severity.WARNING,
        "RELEASE_LOCK() has limited support in TiDB",
        "Use Redis or application-level distributed locking instead",
    ),
    (
        r"\bSQL_CALC_FOUND_ROWS\b", "SQL_CALC_FOUND_ROWS",
        Severity.WARNING,
        "SQL_CALC_FOUND_ROWS is not optimized in TiDB",
        "Use a separate COUNT(*) query instead",
    ),
    (
        r"\bXA\s+(START|BEGIN|END|PREPARE|COMMIT|ROLLBACK)\b", "XA_TRANSACTION",
        Severity.BLOCKER,
        "XA transactions are not supported in TiDB",
        "Redesign to use standard transactions or application-level saga pattern",
    ),
    (
        r"\bFOR\s+UPDATE\s+(NOWAIT|SKIP\s+LOCKED)\b", "FOR_UPDATE_EXTENDED",
        Severity.WARNING,
        "FOR UPDATE NOWAIT/SKIP LOCKED may have limited TiDB support",
        "Verify target TiDB version supports these clauses",
    ),
]


def collect_query_patterns(conn: pymysql.Connection) -> QueryPatterns:
    """Collect and analyze query patterns from performance_schema.

    Returns an empty QueryPatterns if performance_schema is not accessible.
    """
    patterns = QueryPatterns()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT digest_text, count_star, sum_timer_wait,
                       sum_rows_affected, sum_rows_sent, sum_rows_examined
                FROM performance_schema.events_statements_summary_by_digest
                ORDER BY sum_timer_wait DESC
                LIMIT 500
                """
            )
            rows: list[dict[str, Any]] = [
                {k.lower(): v for k, v in row.items()} for row in cur.fetchall()
            ]
    except pymysql.Error as exc:
        logger.warning(
            "Could not read performance_schema (access denied or disabled): %s",
            exc,
        )
        return patterns

    for r in rows:
        digest_text = r.get("digest_text") or ""
        if not digest_text.strip():
            continue

        patterns.digests.append(
            QueryDigest(
                digest_text=digest_text,
                count_star=r.get("count_star") or 0,
                sum_timer_wait=r.get("sum_timer_wait") or 0,
                sum_rows_affected=r.get("sum_rows_affected") or 0,
                sum_rows_sent=r.get("sum_rows_sent") or 0,
                sum_rows_examined=r.get("sum_rows_examined") or 0,
            )
        )

    patterns.total_digests_analyzed = len(patterns.digests)

    # Analyze each digest for incompatible constructs.
    for digest in patterns.digests:
        # Replace ? placeholders with 1 so sqlglot can parse if needed.
        normalized = digest.digest_text.replace("?", "1")

        for regex, construct, severity, message, suggestion in _INCOMPATIBLE_PATTERNS:
            if re.search(regex, normalized, re.IGNORECASE):
                patterns.issues.append(
                    QueryIssue(
                        digest_text=digest.digest_text,
                        construct=construct,
                        severity=severity,
                        message=message,
                        suggestion=suggestion,
                    )
                )

    logger.info(
        "Analyzed %d query digests, found %d issues",
        patterns.total_digests_analyzed,
        len(patterns.issues),
    )
    return patterns
