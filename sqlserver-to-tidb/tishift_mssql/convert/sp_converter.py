"""Stored procedure converter wrapper."""

from __future__ import annotations

from pathlib import Path

from tishift_mssql.convert.procedures import generate_procedure_stubs


def convert_stored_procedures(scan_report: dict[str, object], output_dir: Path, language: str, ai_enabled: bool):
    """Generate procedure conversion artifacts."""
    return generate_procedure_stubs(scan_report, output_dir, language, ai_enabled)
