"""Checksum checker placeholder."""

from __future__ import annotations

from tishift_mssql.check.models import TableMismatch


def compare_checksums(source_checksums: dict[str, str], target_checksums: dict[str, str]) -> list[TableMismatch]:
    """Compare table-level checksums."""
    mismatches: list[TableMismatch] = []
    for table, source_checksum in source_checksums.items():
        target_checksum = target_checksums.get(table)
        if target_checksum is None:
            continue
        if source_checksum != target_checksum:
            mismatches.append(TableMismatch(table, "checksum", "Table checksum mismatch"))
    return mismatches
