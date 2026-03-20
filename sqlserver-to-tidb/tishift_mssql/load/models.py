"""Data models for load command."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LoadPlan:
    strategy: str
    tables: list[str] = field(default_factory=list)
    excluded_tables: list[str] = field(default_factory=list)
    concurrency: int = 4
    schema_first: bool = True
    drop_indexes: bool = True
    schema_mapping: str = "flatten"


@dataclass
class LoadResult:
    strategy: str
    total_tables: int = 0
    loaded_tables: list[str] = field(default_factory=list)
    skipped_tables: list[str] = field(default_factory=list)
    continuation_token: str | None = None
    notes: list[str] = field(default_factory=list)
