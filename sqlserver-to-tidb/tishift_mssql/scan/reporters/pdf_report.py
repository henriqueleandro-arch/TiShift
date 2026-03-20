"""PDF report placeholder using HTML fallback."""

from __future__ import annotations

from pathlib import Path

from tishift_mssql.scan.reporters.html_report import generate_html_report


def generate_pdf_report(report, output_path: Path) -> None:
    """Persist HTML as .pdf placeholder until WeasyPrint integration."""
    html = generate_html_report(report)
    output_path.write_text("PDF generation placeholder. Rendered HTML follows:\n\n" + html)
