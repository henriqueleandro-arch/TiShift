"""Tests for the tishift feedback CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from tishift.cli import main


@pytest.fixture()
def runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary runs directory with sample JSONL log files."""
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr("tishift.run_logger.RUNS_DIR", runs)
    monkeypatch.setattr("tishift.cli.feedback_cmd.RUNS_DIR", runs)

    # Write two sample log files
    log1 = runs / "2026-02-24T03-10-00Z-scan-aabbccdd.jsonl"
    log1.write_text(
        json.dumps({"run_id": "aabbccdd", "phase": "scan", "step": "start", "outcome": "started", "timestamp": "2026-02-24T03:10:00Z", "duration_ms": None, "metrics": {}, "error": None, "tishift_version": "0.1.0"}) + "\n"
        + json.dumps({"run_id": "aabbccdd", "phase": "scan", "step": "complete", "outcome": "ok", "timestamp": "2026-02-24T03:10:02Z", "duration_ms": 2100, "metrics": {"overall_score": 63, "rating": "moderate"}, "error": None, "tishift_version": "0.1.0"}) + "\n"
    )

    log2 = runs / "2026-02-24T03-20-00Z-convert-11223344.jsonl"
    log2.write_text(
        json.dumps({"run_id": "11223344", "phase": "convert", "step": "start", "outcome": "started", "timestamp": "2026-02-24T03:20:00Z", "duration_ms": None, "metrics": {}, "error": None, "tishift_version": "0.1.0"}) + "\n"
        + json.dumps({"run_id": "11223344", "phase": "convert", "step": "complete", "outcome": "ok", "timestamp": "2026-02-24T03:20:05Z", "duration_ms": 5000, "metrics": {"tables_converted": 10}, "error": None, "tishift_version": "0.1.0"}) + "\n"
    )
    return runs


class TestFeedbackCommand:
    def test_feedback_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["feedback", "--help"])
        assert result.exit_code == 0
        assert "Browse and export" in result.output

    def test_feedback_list(self, runs_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["feedback", "--list"])
        assert result.exit_code == 0
        assert "scan" in result.output
        assert "convert" in result.output
        assert "63" in result.output  # score from scan log

    def test_feedback_export(self, runs_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["feedback", "--export"])
        assert result.exit_code == 0

        events = json.loads(result.output)
        assert len(events) == 2
        assert events[0]["phase"] == "convert"  # latest file
        assert events[1]["step"] == "complete"

    def test_feedback_no_flags(self, runs_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["feedback"])
        assert result.exit_code == 0
        assert "--list" in result.output

    def test_feedback_no_runs_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        nonexistent = tmp_path / "does_not_exist" / "runs"
        monkeypatch.setattr("tishift.cli.feedback_cmd.RUNS_DIR", nonexistent)
        runner = CliRunner()
        result = runner.invoke(main, ["feedback", "--list"])
        assert result.exit_code != 0
        assert "No run logs found" in result.output
