"""Simple SQL diff generator."""

from __future__ import annotations

import difflib


def generate_diff(before_sql: str, after_sql: str) -> str:
    """Generate unified diff text."""
    before = before_sql.splitlines(keepends=True)
    after = after_sql.splitlines(keepends=True)
    return "".join(difflib.unified_diff(before, after, fromfile="before.sql", tofile="after.sql"))
