"""Models for convert command output."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ProcedureArtifact:
    name: str
    language: str
    path: Path


@dataclass
class ConversionResult:
    schema_statements: list[str] = field(default_factory=list)
    schema_warnings: list[str] = field(default_factory=list)
    procedure_artifacts: list[ProcedureArtifact] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
