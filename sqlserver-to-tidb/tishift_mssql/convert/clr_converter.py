"""CLR conversion placeholder."""

from __future__ import annotations

from pathlib import Path


def convert_clr(scan_report: dict[str, object], output_dir: Path) -> Path:
    """Write placeholder CLR replacement guidance."""
    path = output_dir / "clr-replacements.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    assemblies = ((scan_report.get("schema_inventory") or {}).get("assemblies") or [])
    path.write_text("# CLR Replacement\n\n" f"Assemblies detected: {len(assemblies)}\n")
    return path
