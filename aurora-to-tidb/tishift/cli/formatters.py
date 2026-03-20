"""Rich CLI formatters for scan output.

Produces the colored, paneled output matching the spec's CLI output design.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from tishift.models import ScanReport


def _score_style(score: int, max_score: int) -> str:
    """Return a Rich style string based on score percentage."""
    pct = (score / max_score * 100) if max_score else 0
    if pct >= 90:
        return "bold green"
    if pct >= 75:
        return "bold yellow"
    if pct >= 50:
        return "bold dark_orange"
    if pct >= 25:
        return "bold red"
    return "bold dark_red"


def _rating_emoji(rating: str) -> str:
    return {
        "excellent": "🟢",
        "good": "🟡",
        "moderate": "🟠",
        "challenging": "🔴",
        "difficult": "⛔",
    }.get(rating, "")


def format_scan_report(report: ScanReport, console: Console | None = None) -> None:
    """Print the scan report to the console using Rich formatting."""
    if console is None:
        console = Console()

    scoring = report.scoring
    meta = report.aurora_metadata
    profile = report.data_profile
    assessment = report.assessment
    automation = report.automation
    cost = report.cost_analysis

    total_gb = profile.total_data_mb / 1024
    db_count = len({t.table_schema for t in report.schema_inventory.tables})

    # ---- Header ----
    header_lines = [
        f"  Source: {report.source_host}",
        f"  Aurora Version: {meta.aurora_version or 'N/A'} ({meta.mysql_version or 'N/A'})",
        f"  Databases: {db_count} | Tables: {len(report.schema_inventory.tables)} | Total Size: {total_gb:.1f} GB",
    ]

    # ---- Overall Score ----
    style = _score_style(scoring.overall_score, 100)
    emoji = _rating_emoji(scoring.rating.value)
    header_lines.append("")
    header_lines.append(
        f"  Overall Score ─────────────────── {scoring.overall_score}/100 {emoji}"
    )
    header_lines.append("")

    # ---- Category Scores ----
    for cat in [
        scoring.schema_compatibility,
        scoring.data_complexity,
        scoring.query_compatibility,
        scoring.procedural_code,
        scoring.operational_readiness,
    ]:
        if cat is None:
            continue
        cat_emoji = _rating_emoji(
            "excellent" if cat.score / cat.max_score >= 0.9
            else "good" if cat.score / cat.max_score >= 0.75
            else "moderate" if cat.score / cat.max_score >= 0.5
            else "challenging" if cat.score / cat.max_score >= 0.25
            else "difficult"
        )
        label = cat.name.replace("_", " ").title()
        dots = "." * (35 - len(label))
        header_lines.append(
            f"  {label} {dots} {cat.score:>2}/{cat.max_score}  {cat_emoji}"
        )

    # ---- Issues ----
    header_lines.append("")
    header_lines.append(f"  ⛔ BLOCKERS: {len(assessment.blockers)}")
    header_lines.append(f"  ⚠️  WARNINGS: {len(assessment.warnings)}")
    for w in assessment.warnings:
        header_lines.append(f"     • {w.message}")
    header_lines.append(f"  ℹ️  INFO: {len(assessment.info)}")
    for i in assessment.info:
        header_lines.append(f"     • {i.message}")

    # ---- Automation ----
    header_lines.append("")
    header_lines.append(f"  Automation Coverage .......... {automation.fully_automated_pct:.0f}% fully automated")
    header_lines.append(f"  AI-Assisted (needs review) ... {automation.ai_assisted_pct:.0f}%")
    header_lines.append(f"  Manual Required .............. {automation.manual_required_pct:.0f}%")

    if cost is not None:
        header_lines.append("")
        header_lines.append(f"  Current Aurora Cost .......... ~${cost.aurora_monthly_estimate:.0f}/month")
        header_lines.append(f"  Estimated TiDB Cloud Cost .... ~${cost.tidb_monthly_estimate:.0f}/month")
        header_lines.append(f"  Projected Savings ............ ~{cost.savings_pct:.0f}%")

    # ---- TiDB Cloud ----
    is_cloud = report.target == "cloud"
    header_lines.append("")
    header_lines.append("  ── TiDB Cloud ──")
    if is_cloud:
        cloud_benefits = []
        has_fulltext = any(
            idx.index_type.upper() == "FULLTEXT"
            for idx in report.schema_inventory.indexes
        )
        if has_fulltext:
            cloud_benefits.append("FULLTEXT indexes supported natively")
        cloud_benefits.extend([
            "Fully managed — no TiKV/PD infrastructure to maintain",
            "Built-in HTAP with TiFlash for real-time analytics",
            "Serverless auto-scaling — pay only for what you use",
            "TiDB Cloud Import for seamless large-scale data migration",
        ])
        for benefit in cloud_benefits:
            header_lines.append(f"     ✓ {benefit}")
    else:
        header_lines.append("     Consider TiDB Cloud for a fully managed migration path")

    header_lines.append("")
    header_lines.append("  Start free → https://tidbcloud.com/free-trial")
    header_lines.append("  Free Starter tier — no credit card required")

    panel = Panel(
        "\n".join(header_lines),
        title="[bold]TiShift — Migration Readiness Report[/bold]",
        border_style="blue",
        expand=False,
        padding=(1, 2),
    )
    console.print(panel)
