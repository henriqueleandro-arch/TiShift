"""CLI report formatter — plain-text format matching TiShift standard output."""

from __future__ import annotations

from rich.console import Console

from tishift_mssql.models import ScanReport


_RATING_LABEL = {
    "excellent": "Excellent",
    "good": "Good",
    "moderate": "Moderate",
    "challenging": "Challenging",
    "difficult": "Difficult",
}

_BORDER = "  " + "═" * 59
_SEP = "    " + "─" * 57


def render_cli_report(report: ScanReport, console: Console) -> None:
    """Render the scan report as plain text matching the TiShift standard format."""
    scoring = report.scoring
    inv = report.schema_inventory
    auto = report.automation
    meta = report.sqlserver_metadata
    assessment = report.assessment

    total_gb = report.data_profile.total_data_mb / 1024
    sp_count = sum(1 for r in inv.routines if "PROCEDURE" in r.routine_type.upper())
    fn_count = sum(1 for r in inv.routines if "FUNCTION" in r.routine_type.upper())

    out = console.print

    out(_BORDER)
    out("    TiShift — Migration Readiness Report")
    out(_BORDER)
    out("")
    out(f"    Source: {report.source_host}")
    out(f"    SQL Server: {meta.edition or 'unknown'} ({meta.product_version or 'unknown'})")
    out(f"    Database: {report.database}")
    out(f"    Tables: {len(inv.tables)} | Total Size: {total_gb:.1f} GB")

    # ── Scoring Summary ──
    out("")
    out("    SCAN SCORING SUMMARY")
    out(_SEP)
    out(f"    {'Category':<24}{'Score':>5}  {'Max':>3}")
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
        out(f"    {name:<24}{cat.score:>5}  {cat.max_score:>3}")
    out(_SEP)

    rating = _RATING_LABEL.get(scoring.rating.value, scoring.rating.value)
    out(f"    Overall Score   {scoring.overall_score}/100")
    out(f"    Rating          {rating}")

    # ── Findings ──
    out("")
    out("    FINDINGS")
    out(_SEP)

    # Blockers — group by type with count, short description, and action
    blocker_groups: dict[str, list] = {}
    for issue in assessment.blockers:
        blocker_groups.setdefault(issue.type, []).append(issue)

    out(f"    Blockers: {len(assessment.blockers)}")
    if not assessment.blockers:
        out("      (none)")
    for btype, issues in sorted(blocker_groups.items()):
        count = len(issues)
        count_str = f" ({count})" if count > 1 else ""
        # Short description from the first issue
        short_msg = _short_description(issues[0].message)
        out(f"      • {btype}{count_str} — {short_msg}")
        # Action on next line with arrow
        suggestion = issues[0].suggestion
        if suggestion:
            out(f"        → {suggestion}")

    # Warnings — group by type
    warning_groups: dict[str, list] = {}
    for issue in assessment.warnings:
        warning_groups.setdefault(issue.type, []).append(issue)

    out("")
    out(f"    Warnings: {len(assessment.warnings)}")
    for wtype, issues in sorted(warning_groups.items()):
        count = len(issues)
        count_str = f" ({count})" if count > 1 else ""
        short_msg = _short_description(issues[0].message)
        out(f"      • {wtype}{count_str} — {short_msg}")
        suggestion = issues[0].suggestion
        if suggestion:
            out(f"        → {suggestion}")

    # ── Automation Coverage ──
    out("")
    out("    AUTOMATION COVERAGE")
    out(_SEP)

    # Build concise multi-item descriptions like the Aurora format
    auto_items = ", ".join(auto.fully_automated_includes[:6]) if auto.fully_automated_includes else ""
    ai_items = ", ".join(auto.ai_assisted_includes[:3]) if auto.ai_assisted_includes else ""
    manual_items = ", ".join(auto.manual_required_includes[:3]) if auto.manual_required_includes else ""

    _print_automation_line(out, "Automated:", auto.fully_automated_pct, auto_items)
    _print_automation_line(out, "AI-assisted:", auto.ai_assisted_pct, ai_items)
    _print_automation_line(out, "Manual:", auto.manual_required_pct, manual_items)

    # ── Scanned Objects ──
    out("")
    out("    SCANNED OBJECTS")
    out(_SEP)
    routines_total = sp_count + fn_count
    line1 = f"    Tables {len(inv.tables):<4}  Columns {len(inv.columns):<4}  Indexes {len(inv.indexes)}"
    out(line1)
    line2_parts = [f"Routines {routines_total}", f"Triggers {len(inv.triggers)}", f"Views {len(inv.views)}"]
    if inv.assemblies:
        line2_parts.append(f"CLR {len(inv.assemblies)}")
    if inv.agent_jobs:
        line2_parts.append(f"Jobs {len(inv.agent_jobs)}")
    out("    " + "   ".join(line2_parts))

    # ── Cost Comparison (optional) ──
    if report.cost_estimate:
        cost = report.cost_estimate
        out("")
        out("    COST COMPARISON")
        out(_SEP)
        out(f"    Current SQL Server Monthly:  ~${cost.estimated_monthly_sqlserver_license_usd:,.0f}")
        if cost.estimated_monthly_tidb_cloud_usd > 0:
            out(f"    Estimated TiDB Cloud:         ~${cost.estimated_monthly_tidb_cloud_usd:,.0f}")
            if cost.estimated_monthly_sqlserver_license_usd > 0:
                savings = (
                    (cost.estimated_monthly_sqlserver_license_usd - cost.estimated_monthly_tidb_cloud_usd)
                    / cost.estimated_monthly_sqlserver_license_usd * 100
                )
                out(f"    Projected Savings:            ~{savings:.0f}%")

    # ── CTA ──
    out("")
    out(_SEP)
    out("    TiDB Cloud Starter — free tier, no credit card required")
    out("    https://tidbcloud.com/free-trial")
    out(_BORDER)
    out("")

    # ── Score breakdown (below the report box) ──
    out("  Score breakdown:")
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
            penalty = cat.max_score - cat.score
            out(f"  - {name} ({cat.score}/{cat.max_score}): {deductions_str} = -{penalty}")
        else:
            out(f"  - {name} ({cat.score}/{cat.max_score}): no deductions")
    out("")


def _short_description(message: str) -> str:
    """Truncate a long issue message to a concise form."""
    # Take the first sentence or up to 60 chars
    if ". " in message:
        return message.split(". ")[0] + "."
    if len(message) > 65:
        return message[:62] + "..."
    return message


def _print_automation_line(out, label: str, pct: float, description: str) -> None:
    """Print an automation line with percentage and wrapped description."""
    first_line = f"    {label:<14}{pct:>3.0f}%"
    if description:
        first_line += f" — {description}"
    # Wrap if too long
    if len(first_line) > 70:
        # Split at a reasonable point
        cut = first_line.rfind(",", 0, 68)
        if cut == -1:
            cut = first_line.rfind(" ", 0, 68)
        if cut > 20:
            out(first_line[:cut + 1])
            remainder = first_line[cut + 1:].strip()
            out(f"{'':>20}{remainder}")
        else:
            out(first_line)
    else:
        out(first_line)
