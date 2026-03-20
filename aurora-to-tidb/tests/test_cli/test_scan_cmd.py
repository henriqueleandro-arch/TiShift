"""Tests for the tishift scan CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from tishift.cli import main
from tishift.models import ScanReport


@pytest.fixture
def config_file(tmp_path):
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


@pytest.fixture
def mock_scan_report(sample_inventory, sample_data_profile, sample_aurora_metadata):
    from tishift.core.scan.analyzers.automation import compute_automation
    from tishift.core.scan.analyzers.compatibility import assess_compatibility
    from tishift.core.scan.analyzers.scoring import compute_scores

    report = ScanReport(
        source_host="localhost",
        database="testdb",
        schema_inventory=sample_inventory,
        data_profile=sample_data_profile,
        aurora_metadata=sample_aurora_metadata,
    )
    report.assessment = assess_compatibility(sample_inventory)
    report.scoring = compute_scores(
        sample_inventory, sample_data_profile, sample_aurora_metadata
    )
    report.automation = compute_automation(sample_inventory)
    return report


class TestScanCommand:
    def test_scan_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["scan", "--help"])
        assert result.exit_code == 0
        assert "Scan Aurora MySQL" in result.output

    @patch("tishift.cli.scan_cmd.get_source_connection")
    @patch("tishift.cli.scan_cmd.run_scan")
    def test_scan_runs(self, mock_run, mock_conn, config_file, mock_scan_report):
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_run.return_value = mock_scan_report

        runner = CliRunner()
        result = runner.invoke(main, [
            "scan", "--config", str(config_file), "--format", "cli", "--quiet", "--ai", "--sample-rows", "5"
        ])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        kwargs = mock_run.call_args.kwargs
        assert kwargs["include_ai"] is True
        assert kwargs["sample_rows"] == 5

    @patch("tishift.cli.scan_cmd.get_source_connection")
    @patch("tishift.cli.scan_cmd.run_scan")
    def test_scan_json_output(self, mock_run, mock_conn, config_file, mock_scan_report, tmp_path):
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_run.return_value = mock_scan_report

        runner = CliRunner()
        result = runner.invoke(main, [
            "scan", "--config", str(config_file),
            "--format", "json",
            "--output-dir", str(tmp_path),
            "--quiet",
        ])
        assert result.exit_code == 0
        assert (tmp_path / "tishift-report.json").exists()

    @patch("tishift.cli.scan_cmd.get_source_connection")
    @patch("tishift.cli.scan_cmd.run_scan")
    def test_scan_html_output(self, mock_run, mock_conn, config_file, mock_scan_report, tmp_path):
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_run.return_value = mock_scan_report

        runner = CliRunner()
        result = runner.invoke(main, [
            "scan", "--config", str(config_file),
            "--format", "html",
            "--output-dir", str(tmp_path),
            "--quiet",
        ])
        assert result.exit_code == 0
        assert (tmp_path / "tishift-report.html").exists()
