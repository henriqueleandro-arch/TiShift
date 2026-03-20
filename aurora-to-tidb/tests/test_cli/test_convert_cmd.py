"""Tests for tishift convert CLI."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from tishift.cli import main
from tishift.core.scan.analyzers.automation import compute_automation
from tishift.core.scan.analyzers.compatibility import assess_compatibility
from tishift.core.scan.analyzers.scoring import compute_scores
from tishift.core.scan.reporters.json_report import generate_json_report
from tishift.models import ScanReport


def test_convert_generates_outputs(tmp_path, sample_inventory, sample_data_profile, sample_aurora_metadata):
    report = ScanReport(
        source_host="aurora-test.example.com",
        database="tishift_test",
        schema_inventory=sample_inventory,
        data_profile=sample_data_profile,
        aurora_metadata=sample_aurora_metadata,
    )
    report.assessment = assess_compatibility(sample_inventory)
    report.scoring = compute_scores(sample_inventory, sample_data_profile, sample_aurora_metadata)
    report.automation = compute_automation(sample_inventory)
    report_data = generate_json_report(report)
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report_data))

    cfg_path = tmp_path / "tishift.yaml"
    cfg_path.write_text(
        "source:\n"
        "  host: localhost\n"
        "  port: 3306\n"
        "  user: root\n"
        "  password: test\n"
        "  database: testdb\n"
    )

    out_dir = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(main, [
        "convert",
        "--config", str(cfg_path),
        "--scan-report", str(report_path),
        "--output-dir", str(out_dir),
    ])
    assert result.exit_code == 0
    assert (out_dir / "schema" / "01-create-tables.sql").exists()
    assert (out_dir / "procedures").exists()
