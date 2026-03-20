"""PDF report generator using WeasyPrint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from tishift.core.scan.reporters.json_report import generate_json_report
from tishift.models import ScanReport

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def generate_executive_pdf(report: ScanReport) -> bytes:
    """Generate an executive summary PDF (2-3 pages)."""
    try:
        from weasyprint import HTML  # type: ignore
    except ImportError as exc:
        raise RuntimeError("weasyprint dependency not installed; install tishift[pdf]") from exc

    data = generate_json_report(report)

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("executive.html.j2")
    html = template.render(**data)

    return HTML(string=html).write_pdf()
