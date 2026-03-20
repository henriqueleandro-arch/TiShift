"""Stored procedure conversion scaffolding."""

from __future__ import annotations

from pathlib import Path

from tishift_mssql.convert.models import ProcedureArtifact


_EXT = {
    "python": "py",
    "go": "go",
    "java": "java",
    "javascript": "js",
}


def _sanitize(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in name)


def generate_procedure_stubs(
    scan_report: dict[str, object],
    output_dir: Path,
    language: str,
    ai_enabled: bool,
) -> list[ProcedureArtifact]:
    """Generate language-specific stubs for SQL Server procedures."""
    inventory = scan_report.get("schema_inventory")
    if not isinstance(inventory, dict):
        return []
    routines = inventory.get("routines")
    if not isinstance(routines, list):
        return []

    ext = _EXT.get(language, "txt")
    procedures_dir = output_dir / "procedures"
    procedures_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[ProcedureArtifact] = []
    for routine in routines:
        if not isinstance(routine, dict):
            continue
        routine_type = str(routine.get("routine_type") or "")
        if "PROCEDURE" not in routine_type.upper():
            continue

        schema_name = str(routine.get("schema_name") or "dbo")
        routine_name = str(routine.get("routine_name") or "unnamed_proc")
        definition = str(routine.get("definition") or "")

        filename = f"{_sanitize(schema_name)}_{_sanitize(routine_name)}.{ext}"
        output_path = procedures_dir / filename
        mode_note = "AI-assisted placeholder" if ai_enabled else "rule-based placeholder"

        output_path.write_text(
            f"// {mode_note}\n"
            f"// Source: {schema_name}.{routine_name}\n"
            "// TiDB does not execute stored procedures. Move this logic to application services.\n\n"
            f"/* Original T-SQL\n{definition}\n*/\n"
        )
        artifacts.append(ProcedureArtifact(name=f"{schema_name}.{routine_name}", language=language, path=output_path))

    return artifacts
