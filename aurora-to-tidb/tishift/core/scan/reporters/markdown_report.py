"""Markdown report generator."""

from __future__ import annotations

from tishift.core.scan.reporters.json_report import generate_json_report
from tishift.models import ScanReport


def generate_markdown_report(report: ScanReport) -> str:
    data = generate_json_report(report)

    lines: list[str] = []
    lines.append("# TiShift Migration Readiness Report")
    lines.append("")
    lines.append(f"- Generated at: {data['generated_at']}")
    lines.append(f"- Source: {data['source']['host']}")
    lines.append(f"- Aurora Version: {data['source']['aurora_version']}")
    lines.append(f"- MySQL Version: {data['source']['mysql_version']}")
    lines.append("")

    summary = data["summary"]
    lines.append("## Summary")
    lines.append(f"- Overall score: {summary['overall_score']}/100 ({summary['rating']})")
    lines.append(f"- Databases: {summary['database_count']}")
    lines.append(f"- Tables: {summary['table_count']}")
    lines.append(f"- Data size (GB): {summary['total_data_size_gb']}")
    lines.append("")

    lines.append("## Scores")
    for name, score in data["scores"].items():
        lines.append(f"- {name.replace('_', ' ').title()}: {score['score']}/{score['max']}")
    lines.append("")

    issues = data["issues"]
    lines.append("## Issues")
    lines.append(f"- Blockers: {len(issues['blockers'])}")
    lines.append(f"- Warnings: {len(issues['warnings'])}")
    lines.append(f"- Info: {len(issues['info'])}")
    lines.append("")

    if data.get("cost_analysis"):
        cost = data["cost_analysis"]
        lines.append("## Cost Analysis")
        lines.append(f"- Aurora monthly: ${cost['aurora_monthly_estimate']:.2f}")
        lines.append(f"- TiDB monthly: ${cost['tidb_monthly_estimate']:.2f}")
        lines.append(f"- Savings: {cost['savings_pct']}%")
        lines.append("")

    return "\n".join(lines)
