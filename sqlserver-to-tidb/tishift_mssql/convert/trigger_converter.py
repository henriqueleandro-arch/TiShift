"""Trigger conversion placeholder."""

from __future__ import annotations

from pathlib import Path


def convert_triggers(scan_report: dict[str, object], output_dir: Path) -> Path:
    """Write placeholder trigger migration notes."""
    path = output_dir / "triggers-middleware.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    triggers = ((scan_report.get("schema_inventory") or {}).get("triggers") or [])
    path.write_text("# Trigger Conversion\n\n" f"Triggers detected: {len(triggers)}\n")
    return path
