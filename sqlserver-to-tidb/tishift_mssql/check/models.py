"""Data models for check command."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TableMismatch:
    table: str
    issue: str
    details: str


@dataclass
class CheckResult:
    tables_checked: int = 0
    schema_mismatches: list[TableMismatch] = field(default_factory=list)
    row_count_mismatches: list[TableMismatch] = field(default_factory=list)
    row_mismatches: list[TableMismatch] = field(default_factory=list)
    checksum_mismatches: list[TableMismatch] = field(default_factory=list)
    passed: bool = True
