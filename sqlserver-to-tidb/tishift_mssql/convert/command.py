"""Convert command orchestration."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from tishift_mssql.config import TiShiftMSSQLConfig
from tishift_mssql.connection import get_target_connection
from tishift_mssql.convert.loader import load_scan_report
from tishift_mssql.convert.models import ConversionResult
from tishift_mssql.convert.procedures import generate_procedure_stubs
from tishift_mssql.convert.schema import generate_schema_ddl


def _write_schema_outputs(output_dir: Path, statements: list[str], warnings: list[str]) -> None:
    schema_dir = output_dir / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "schema.sql").write_text("\n\n".join(statements) + "\n")

    report_lines = ["# Type Mapping Report", "", f"Generated statements: {len(statements)}"]
    if warnings:
        report_lines.extend(["", "## Warnings"])
        for warning in warnings:
            report_lines.append(f"- {warning}")
    (schema_dir / "type-mapping-report.md").write_text("\n".join(report_lines) + "\n")


def _apply_schema(config: TiShiftMSSQLConfig, statements: list[str]) -> None:
    if not statements:
        return
    with get_target_connection(config.target) as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
        conn.commit()


def run_convert(
    *,
    config: TiShiftMSSQLConfig | None,
    scan_report_path: Path,
    output_dir: Path,
    sp_only: bool,
    schema_only: bool,
    ai_enabled: bool,
    language: str,
    apply: bool,
    dry_run: bool,
    schema_mapping: str,
    console: Console | None,
) -> ConversionResult:
    """Run conversion pipeline from scan report to output artifacts."""
    if sp_only and schema_only:
        raise ValueError("--sp-only and --schema-only cannot be used together")

    scan_report = load_scan_report(scan_report_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = ConversionResult()

    if not sp_only:
        statements, warnings = generate_schema_ddl(scan_report, schema_mapping)
        result.schema_statements = statements
        result.schema_warnings = warnings
        _write_schema_outputs(output_dir, statements, warnings)

        if dry_run and console:
            console.print("[bold]Schema dry-run output:[/bold]")
            for statement in statements[:20]:
                console.print(statement)

        if apply:
            if config is None:
                raise ValueError("--apply requires --config")
            _apply_schema(config, statements)
            result.notes.append("Applied schema statements to target TiDB")

    if not schema_only:
        result.procedure_artifacts = generate_procedure_stubs(scan_report, output_dir, language, ai_enabled)

    notes = [
        "# Conversion Notes",
        "",
        f"Schema statements: {len(result.schema_statements)}",
        f"Procedure artifacts: {len(result.procedure_artifacts)}",
        f"AI enabled: {ai_enabled}",
        f"Schema mapping: {schema_mapping}",
    ]
    if result.schema_warnings:
        notes.extend(["", "## Warnings", *[f"- {warning}" for warning in result.schema_warnings]])
    (output_dir / "conversion-notes.md").write_text("\n".join(notes) + "\n")

    manifest = {
        "scan_report": str(scan_report_path),
        "schema_statements": len(result.schema_statements),
        "schema_warnings": result.schema_warnings,
        "procedure_artifacts": [str(item.path) for item in result.procedure_artifacts],
        "notes": result.notes,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    return result
