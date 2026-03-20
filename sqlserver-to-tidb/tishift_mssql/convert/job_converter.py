"""SQL Agent job conversion placeholder."""

from __future__ import annotations

from pathlib import Path


def convert_jobs(scan_report: dict[str, object], output_dir: Path) -> Path:
    """Write placeholder cron/Airflow migration plan."""
    path = output_dir / "agent-jobs.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    jobs = ((scan_report.get("schema_inventory") or {}).get("agent_jobs") or [])
    path.write_text("# SQL Agent Jobs\n\n" f"Jobs detected: {len(jobs)}\n")
    return path
