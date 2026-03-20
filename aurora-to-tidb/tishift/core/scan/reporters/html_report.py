"""HTML report generator.

Uses Jinja2 to render a self-contained HTML report with inline CSS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from tishift.core.scan.reporters.json_report import generate_json_report
from tishift.models import ScanReport

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _score_color(score: int, max_score: int) -> str:
    """Return a CSS color based on score percentage."""
    pct = (score / max_score * 100) if max_score else 0
    if pct >= 90:
        return "#22c55e"  # green
    if pct >= 75:
        return "#eab308"  # yellow
    if pct >= 50:
        return "#f97316"  # orange
    if pct >= 25:
        return "#ef4444"  # red
    return "#991b1b"  # dark red


def _rating_emoji(rating: str) -> str:
    """Return the emoji for a rating level."""
    return {
        "excellent": "🟢",
        "good": "🟡",
        "moderate": "🟠",
        "challenging": "🔴",
        "difficult": "⛔",
    }.get(rating, "")


def generate_html_report(report: ScanReport) -> str:
    """Render the ScanReport as a self-contained HTML string."""
    data = generate_json_report(report)

    # Add template helpers.
    data["score_color"] = _score_color
    data["rating_emoji"] = _rating_emoji(data["summary"]["rating"])
    data["overall_color"] = _score_color(
        data["summary"]["overall_score"], 100
    )

    # Score details with colors.
    for cat_name, cat_data in data["scores"].items():
        cat_data["color"] = _score_color(cat_data["score"], cat_data["max"])

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("report.html.j2")
    return template.render(**data)
