"""Schema diff generator."""

from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass
class DiffResult:
    unified_diff: str
    html_diff: str


def generate_schema_diff(original_sql: str, converted_sql: str) -> DiffResult:
    """Generate unified and HTML diffs between original and converted DDL."""
    original_lines = original_sql.splitlines()
    converted_lines = converted_sql.splitlines()
    diff = difflib.unified_diff(
        original_lines,
        converted_lines,
        fromfile="aurora.sql",
        tofile="tidb.sql",
        lineterm="",
    )
    unified = "\n".join(diff) + "\n"

    html = difflib.HtmlDiff(wrapcolumn=100).make_file(
        original_lines,
        converted_lines,
        fromdesc="Aurora",
        todesc="TiDB",
        context=True,
        numlines=3,
    )
    return DiffResult(unified_diff=unified, html_diff=html)
