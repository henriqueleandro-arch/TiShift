"""Row-level checker placeholder with normalization hooks."""

from __future__ import annotations

import hashlib
import json

from tishift_mssql.check.models import TableMismatch


def _normalize(value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value


def _row_hash(row: dict[str, object]) -> str:
    normalized = {k: _normalize(v) for k, v in sorted(row.items())}
    encoded = json.dumps(normalized, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compare_rows(
    source_rows: dict[str, list[dict[str, object]]],
    target_rows: dict[str, list[dict[str, object]]],
    sample_rate: float,
) -> list[TableMismatch]:
    """Compare hashed row payloads with optional sampling."""
    mismatches: list[TableMismatch] = []
    for table, rows in source_rows.items():
        tgt_rows = target_rows.get(table)
        if tgt_rows is None:
            continue

        src = rows
        tgt = tgt_rows
        if sample_rate < 1.0:
            size = max(1, int(len(src) * sample_rate))
            src = src[:size]
            tgt = tgt[:size]

        src_hashes = [_row_hash(r) for r in src]
        tgt_hashes = [_row_hash(r) for r in tgt]
        if src_hashes != tgt_hashes:
            mismatches.append(TableMismatch(table, "row_hash", "Row-level hash comparison differs"))
    return mismatches
