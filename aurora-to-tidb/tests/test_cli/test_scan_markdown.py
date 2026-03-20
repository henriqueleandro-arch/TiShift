"""Markdown report CLI test."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from tishift.cli import main
from tishift.models import ScanReport


def _config_file(tmp_path: Path) -> Path:
    cfg = tmp_path / "tishift.yaml"
    cfg.write_text(
        "source:\n"
        "  host: localhost\n"
        "  port: 3306\n"
        "  user: root\n"
        "  password: test\n"
        "  database: testdb\n"
    )
    return cfg


def _minimal_report() -> ScanReport:
    return ScanReport(source_host="localhost", database="testdb")


@patch("tishift.cli.scan_cmd.get_source_connection")
@patch("tishift.cli.scan_cmd.run_scan")
def test_scan_markdown_output(mock_run, mock_conn, tmp_path):
    mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_conn.return_value.__exit__ = MagicMock(return_value=False)
    mock_run.return_value = _minimal_report()

    cfg = _config_file(tmp_path)
    out_dir = tmp_path / "reports"

    runner = CliRunner()
    result = runner.invoke(main, [
        "scan",
        "--config", str(cfg),
        "--format", "markdown",
        "--output-dir", str(out_dir),
        "--quiet",
    ])

    assert result.exit_code == 0
    assert (out_dir / "tishift-report.md").exists()
