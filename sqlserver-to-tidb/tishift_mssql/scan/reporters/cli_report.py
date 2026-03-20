"""CLI report formatter — matches the Aurora TiShift report style."""

from __future__ import annotations

from collections import Counter

from rich.console import Console
from rich.panel import Panel

from tishift_mssql.models import ScanReport, Severity


_RATING_LABEL = {
    "excellent": "Excellent",
    "good": "Good",
    "moderate": "Moderate",
    "challenging": "Challenging",
    "difficult": "Difficult",
}

_SEP = "    " + "─" * 57


def render_cli_report(report: ScanReport, console: Console) -> None:
    """Render the scan report in the unified TiShift report style."""
    scoring = report.scoring
    inv = report.schema_inventory
    auto = report.automation
    meta = report.sqlserver_metadata
    assessment = report.assessment

    lines: list[str] = []

    # ── Header ──
    lines.append(f"    Source: {report.source_host}")
    version_str = meta.product_version or "unknown"
    edition_str = meta.edition or "unknown"
    lines.append(f"    SQL Server: {edition_str} ({version_str})")
    total_gb = report.data_profile.total_data_mb / 1024
    lines.append(
        f"    Database: {report.database}"
    )
    lines.append(
        f"    Tables: {len(inv.tables)} | Total Size: {total_gb:.1f} GB"
    )

    # ── Scoring Summary ──
    lines.append("")
    lines.append("    SCAN SCORING SUMMARY")
    lines.append(_SEP)
    lines.append(f"    {'Category':<24} {'Score':>5}  {'Max':>3}")
    for cat in [
        scoring.schema_compatibility,
        scoring.data_complexity,
        scoring.query_compatibility,
        scoring.code_portability,
        scoring.operational_readiness,
    ]:
        if cat is None:
            continue
        name = "Operational" if "Operational" in cat.name else cat.name
        lines.append(f"    {name:<24} {cat.score:>5}  {cat.max_score:>3}")

    lines.append(_SEP)
    rating = _RATING_LABEL.get(scoring.rating.value, scoring.rating.value)
    lines.append(f"    Overall Score   {scoring.overall_score}/100")
    lines.append(f"    Rating          {rating}")

    # ── Findings ──
    lines.append("")
    lines.append("    FINDINGS")
    lines.append(_SEP)

    # Blockers — group by type with counts and actions
    blocker_groups: dict[str, list] = {}
    for issue in assessment.blockers:
        blocker_groups.setdefault(issue.type, []).append(issue)

    lines.append(f"    Blockers: {len(assessment.blockers)}")
    if not assessment.blockers:
        lines.append("      (none)")
    for btype, issues in sorted(blocker_groups.items()):
        msg = issues[0].message
        suggestion = issues[0].suggestion or ""
        count_str = f" ({len(issues)})" if len(issues) > 1 else ""
        lines.append(f"      • {btype}{count_str} — {msg}")
        if suggestion:
            lines.append(f"        → {suggestion}")

    # Warnings — group by type
    warning_groups: dict[str, list] = {}
    for issue in assessment.warnings:
        warning_groups.setdefault(issue.type, []).append(issue)

    lines.append("")
    lines.append(f"    Warnings: {len(assessment.warnings)}")
    for wtype, issues in sorted(warning_groups.items()):
        msg = issues[0].message
        count_str = f" ({len(issues)})" if len(issues) > 1 else ""
        suggestion = issues[0].suggestion or ""
        lines.append(f"      • {wtype}{count_str} — {msg}")
        if suggestion:
            lines.append(f"        → {suggestion}")

    # ── Automation Coverage ──
    lines.append("")
    lines.append("    AUTOMATION COVERAGE")
    lines.append(_SEP)

    # Build descriptive includes
    auto_desc = ", ".join(auto.fully_automated_includes[:4]) if auto.fully_automated_includes else ""
    ai_desc = ", ".join(auto.ai_assisted_includes[:2]) if auto.ai_assisted_includes else ""
    manual_desc = ", ".join(auto.manual_required_includes[:3]) if auto.manual_required_includes else ""

    lines.append(f"    Automated:    {auto.fully_automated_pct:>3.0f}%")
    if auto_desc:
        # Wrap long descriptions
        _append_wrapped(lines, auto_desc, indent=18, width=52)
    lines.append(f"    AI-assisted:  {auto.ai_assisted_pct:>3.0f}%")
    if ai_desc:
        _append_wrapped(lines, ai_desc, indent=18, width=52)
    lines.append(f"    Manual:       {auto.manual_required_pct:>3.0f}%")
    if manual_desc:
        _append_wrapped(lines, manual_desc, indent=18, width=52)

    # ── Scanned Objects ──
    lines.append("")
    lines.append("    SCANNED OBJECTS")
    lines.append(_SEP)
    sp_count = sum(1 for r in inv.routines if "PROCEDURE" in r.routine_type.upper())
    fn_count = sum(1 for r in inv.routines if "FUNCTION" in r.routine_type.upper())
    routines_total = sp_count + fn_count
    lines.append(
        f"    Tables {len(inv.tables):<4}  Columns {len(inv.columns):<4}  "
        f"Indexes {len(inv.indexes)}"
    )
    lines.append(
        f"    Routines {routines_total:<2}  Triggers {len(inv.triggers):<2}  "
        f"Views {len(inv.views)}"
    )
    if inv.assemblies:
        lines.append(f"    CLR Assemblies {len(inv.assemblies)}  Agent Jobs {len(inv.agent_jobs)}")

    # ── Cost Estimate (optional) ──
    if report.cost_estimate:
        cost = report.cost_estimate
        lines.append("")
        lines.append("    COST COMPARISON")
        lines.append(_SEP)
        lines.append(f"    Current SQL Server Monthly:  ~${cost.estimated_monthly_sqlserver_license_usd:,.0f}")
        if cost.estimated_monthly_tidb_cloud_usd > 0:
            lines.append(f"    Estimated TiDB Cloud:         ~${cost.estimated_monthly_tidb_cloud_usd:,.0f}")
            if cost.estimated_monthly_sqlserver_license_usd > 0:
                savings = (
                    (cost.estimated_monthly_sqlserver_license_usd - cost.estimated_monthly_tidb_cloud_usd)
                    / cost.estimated_monthly_sqlserver_license_usd * 100
                )
                lines.append(f"    Projected Savings:            ~{savings:.0f}%")

    # ── CTA ──
    lines.append("")
    lines.append(_SEP)
    lines.append("    TiDB Cloud Starter — free tier, no credit card required")
    lines.append("    https://tidbcloud.com/free-trial")

    # ── Score Breakdown detail ──
    lines.append("")
    lines.append("  Score breakdown:")
    for cat in [
        scoring.schema_compatibility,
        scoring.code_portability,
        scoring.query_compatibility,
        scoring.data_complexity,
        scoring.operational_readiness,
    ]:
        if cat is None:
            continue
        name = "Operational" if "Operational" in cat.name else cat.name
        if cat.deductions:
            deductions_str = ", ".join(cat.deductions)
            lines.append(f"  - {name} ({cat.score}/{cat.max_score}): {deductions_str}")
        else:
            lines.append(f"  - {name} ({cat.score}/{cat.max_score}): no deductions")

    # Render everything in a single panel
    panel_content = "\n".join(lines)
    console.print(
        Panel(
            panel_content,
            title="[bold]TiShift — Migration Readiness Report[/bold]",
            border_style="bright_blue",
            expand=False,
            padding=(1, 2),
        )
    )
    console.print()


def _append_wrapped(lines: list[str], text: str, indent: int, width: int) -> None:
    """Append text wrapped at width with the given indent."""
    prefix = " " * indent
    words = text.split()
    current_line = prefix
    for word in words:
        if len(current_line) + len(word) + 1 > indent + width:
            lines.append(current_line)
            current_line = prefix + word
        else:
            if current_line == prefix:
                current_line += word
            else:
                current_line += " " + word
    if current_line.strip():
        lines.append(current_line)
