"""HTML report renderer."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from tishift_mssql.models import ScanReport, to_dict


def generate_html_report(report: ScanReport) -> str:
    """Render report HTML from bundled Jinja2 template."""
    templates_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html.j2")
    data = to_dict(report)
    return template.render(report=data)
