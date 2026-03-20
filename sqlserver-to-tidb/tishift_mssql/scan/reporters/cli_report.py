"""CLI report formatter using Rich tables and panels."""

from __future__ import annotations

from collections import Counter

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from tishift_mssql.models import ScanReport, Severity


_RATING_EMOJI = {
    "excellent": "[green]Excellent[/green]",
    "good": "[yellow]Good[/yellow]",
    "moderate": "[dark_orange]Moderate[/dark_orange]",
    "challenging": "[red]Challenging[/red]",
    "difficult": "[bold red]Difficult[/bold red]",
}


def _score_color(score: int, max_score: int) -> str:
    ratio = score / max_score if max_score else 0
    if ratio >= 0.85:
        return "green"
    if ratio >= 0.70:
        return "yellow"
    if ratio >= 0.50:
        return "dark_orange"
    return "red"


def render_cli_report(report: ScanReport, console: Console) -> None:
    """Render the full scan report matching the spec CLI output format."""

    # -- Header panel --
    meta = report.sqlserver_metadata
    version_line = meta.product_version or "unknown"
    edition_line = meta.edition or "unknown"
    header_text = (
        f"Source: {report.source_host}\n"
        f"SQL Server {edition_line} ({version_line})\n"
        f"Database: {report.database}  |  "
        f"Tables: {len(report.schema_inventory.tables)}  |  "
        f"Total Size: {report.data_profile.total_data_mb / 1024:.1f} GB"
    )
    console.print(
        Panel(
            header_text,
            title="[bold]TiShift-SQLServer — Migration Readiness Report[/bold]",
            border_style="bright_blue",
        )
    )

    # -- Overall score --
    rating_label = _RATING_EMOJI.get(report.scoring.rating.value, report.scoring.rating.value)
    console.print(
        f"\n  [bold]Overall Score[/bold]  {report.scoring.overall_score}/100  {rating_label}\n"
    )

    # -- Category scores --
    scores_table = Table(title="Score Breakdown", show_lines=False, pad_edge=True)
    scores_table.add_column("Category", min_width=24)
    scores_table.add_column("Score", justify="right", min_width=8)
    scores_table.add_column("Deductions", ratio=1)

    for cat in [
        report.scoring.schema_compatibility,
        report.scoring.code_portability,
        report.scoring.query_compatibility,
        report.scoring.data_complexity,
        report.scoring.operational_readiness,
    ]:
        if cat is None:
            continue
        color = _score_color(cat.score, cat.max_score)
        deductions_str = "; ".join(cat.deductions[:3]) if cat.deductions else "—"
        if len(cat.deductions) > 3:
            deductions_str += f" (+{len(cat.deductions) - 3} more)"
        scores_table.add_row(
            cat.name,
            f"[{color}]{cat.score}/{cat.max_score}[/{color}]",
            deductions_str,
        )

    console.print(scores_table)

    # -- T-SQL Feature Usage --
    feature_counts: Counter[str] = Counter()
    for usage in report.feature_scan.usages:
        feature_counts[usage.pattern_name] += 1

    if feature_counts:
        console.print("\n[bold]T-SQL Feature Usage[/bold]")
        feat_table = Table(show_header=True, show_lines=False, pad_edge=True)
        feat_table.add_column("Feature", min_width=24)
        feat_table.add_column("Occurrences", justify="right")
        for name, count in feature_counts.most_common():
            feat_table.add_row(name.replace("_", " ").title(), str(count))
        console.print(feat_table)

    # Inventory highlights
    inv = report.schema_inventory
    console.print("\n[bold]Inventory[/bold]")
    inv_table = Table(show_header=False, show_lines=False, pad_edge=True)
    inv_table.add_column("Metric", min_width=28)
    inv_table.add_column("Value", justify="right")
    inv_table.add_row("Stored Procedures", str(sum(1 for r in inv.routines if "PROCEDURE" in r.routine_type.upper())))
    inv_table.add_row("Functions", str(sum(1 for r in inv.routines if "FUNCTION" in r.routine_type.upper())))
    inv_table.add_row("Triggers", str(len(inv.triggers)))
    inv_table.add_row("CLR Assemblies", str(len(inv.assemblies)))
    inv_table.add_row("SQL Agent Jobs", str(len(inv.agent_jobs)))
    inv_table.add_row("Linked Servers", str(len(inv.linked_servers)))
    inv_table.add_row("Views", str(len(inv.views)))
    inv_table.add_row("Schemas in Use", ", ".join(inv.schemas) if inv.schemas else "dbo")
    console.print(inv_table)

    # -- Issues --
    console.print("\n[bold]Issues Found[/bold]")
    if report.assessment.blockers:
        console.print(f"  [bold red]BLOCKERS: {len(report.assessment.blockers)}[/bold red]")
        for issue in report.assessment.blockers[:10]:
            console.print(f"    [red]•[/red] [{issue.type}] {issue.object_name}: {issue.message}")
        if len(report.assessment.blockers) > 10:
            console.print(f"    ... and {len(report.assessment.blockers) - 10} more")
    else:
        console.print("  [green]No blockers found[/green]")

    if report.assessment.warnings:
        console.print(f"  [yellow]WARNINGS: {len(report.assessment.warnings)}[/yellow]")
        for issue in report.assessment.warnings[:10]:
            console.print(f"    [yellow]•[/yellow] [{issue.type}] {issue.object_name}: {issue.message}")
        if len(report.assessment.warnings) > 10:
            console.print(f"    ... and {len(report.assessment.warnings) - 10} more")

    # -- Automation estimates --
    auto = report.automation
    console.print("\n[bold]Automation Estimates[/bold]")
    est_table = Table(show_header=False, show_lines=False, pad_edge=True)
    est_table.add_column("Level", min_width=28)
    est_table.add_column("Pct", justify="right")
    est_table.add_row("Fully Automated", f"{auto.fully_automated_pct:.0f}%")
    est_table.add_row("AI-Assisted (needs review)", f"{auto.ai_assisted_pct:.0f}%")
    est_table.add_row("Manual Required", f"{auto.manual_required_pct:.0f}%")
    console.print(est_table)

    # -- Cost estimate (optional) --
    if report.cost_estimate:
        cost = report.cost_estimate
        console.print("\n[bold]Cost Estimate[/bold]")
        console.print(f"  SQL Server Monthly: ${cost.estimated_monthly_sqlserver_license_usd:,.0f}")
        for assumption in cost.assumptions:
            console.print(f"    • {assumption}")

    console.print()
