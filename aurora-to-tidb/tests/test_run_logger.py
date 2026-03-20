"""Tests for the JSONL run logger and anonymization helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tishift.models import (
    AssessmentResult,
    AutomationCoverage,
    CategoryScore,
    DataProfile,
    Issue,
    ScanReport,
    SchemaInventory,
    ScoringResult,
    Severity,
    TableInfo,
)
from tishift.run_logger import (
    RUNS_DIR,
    RunLogger,
    anonymize_host,
    fingerprint,
    summarize_report,
)


# ---------------------------------------------------------------------------
# anonymize_host
# ---------------------------------------------------------------------------


class TestAnonymizeHost:
    def test_localhost_literal(self) -> None:
        assert anonymize_host("localhost") == "localhost"

    def test_localhost_ip4(self) -> None:
        assert anonymize_host("127.0.0.1") == "localhost"

    def test_localhost_ip6(self) -> None:
        assert anonymize_host("::1") == "localhost"

    def test_rds_hostname(self) -> None:
        assert anonymize_host("mydb.abc123.us-east-1.rds.amazonaws.com") == "aws-rds"

    def test_aurora_cluster(self) -> None:
        assert anonymize_host("mydb.cluster-abc123.us-east-1.rds.amazonaws.com") == "aws-aurora"

    def test_tidb_cloud(self) -> None:
        assert anonymize_host("gateway01.us-east-1.prod.tidbcloud.com") == "tidb-cloud"

    def test_unknown_host(self) -> None:
        assert anonymize_host("db.example.com") == "other"

    def test_case_insensitive(self) -> None:
        assert anonymize_host("MyDB.RDS.AMAZONAWS.COM") == "aws-rds"


# ---------------------------------------------------------------------------
# fingerprint
# ---------------------------------------------------------------------------


class TestFingerprint:
    def test_returns_12_hex_chars(self) -> None:
        result = fingerprint("my_database")
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self) -> None:
        assert fingerprint("test") == fingerprint("test")

    def test_different_inputs_differ(self) -> None:
        assert fingerprint("foo") != fingerprint("bar")


# ---------------------------------------------------------------------------
# RunLogger
# ---------------------------------------------------------------------------


class TestRunLogger:
    def test_creates_runs_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        runs = tmp_path / "runs"
        monkeypatch.setattr("tishift.run_logger.RUNS_DIR", runs)
        logger = RunLogger(phase="scan")
        assert runs.exists()

    def test_writes_jsonl_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        runs = tmp_path / "runs"
        monkeypatch.setattr("tishift.run_logger.RUNS_DIR", runs)
        logger = RunLogger(phase="scan")
        logger.started()
        logger.completed(metrics={"score": 80}, duration_ms=1200)

        files = list(runs.glob("*.jsonl"))
        assert len(files) == 1

        lines = files[0].read_text().strip().splitlines()
        assert len(lines) == 2

        start_event = json.loads(lines[0])
        assert start_event["step"] == "start"
        assert start_event["outcome"] == "started"
        assert start_event["phase"] == "scan"
        assert start_event["duration_ms"] is None

        complete_event = json.loads(lines[1])
        assert complete_event["step"] == "complete"
        assert complete_event["outcome"] == "ok"
        assert complete_event["metrics"]["score"] == 80
        assert complete_event["duration_ms"] == 1200

    def test_failed_logs_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        runs = tmp_path / "runs"
        monkeypatch.setattr("tishift.run_logger.RUNS_DIR", runs)
        logger = RunLogger(phase="scan")
        logger.failed(ValueError("connection refused"), duration_ms=50)

        files = list(runs.glob("*.jsonl"))
        lines = files[0].read_text().strip().splitlines()
        event = json.loads(lines[0])
        assert event["outcome"] == "error"
        assert "ValueError" in event["error"]
        assert "connection refused" in event["error"]

    def test_step_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        runs = tmp_path / "runs"
        monkeypatch.setattr("tishift.run_logger.RUNS_DIR", runs)
        logger = RunLogger(phase="scan")
        logger.step_ok("schema_collect", {"table_count": 10}, duration_ms=850)

        files = list(runs.glob("*.jsonl"))
        lines = files[0].read_text().strip().splitlines()
        event = json.loads(lines[0])
        assert event["step"] == "schema_collect"
        assert event["outcome"] == "ok"
        assert event["metrics"]["table_count"] == 10

    def test_filename_contains_phase_and_run_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        runs = tmp_path / "runs"
        monkeypatch.setattr("tishift.run_logger.RUNS_DIR", runs)
        logger = RunLogger(run_id="abcdef1234567890", phase="convert")
        logger.started()

        files = list(runs.glob("*.jsonl"))
        assert len(files) == 1
        assert "convert" in files[0].name
        assert "abcdef12" in files[0].name

    def test_events_have_tishift_version(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        runs = tmp_path / "runs"
        monkeypatch.setattr("tishift.run_logger.RUNS_DIR", runs)
        logger = RunLogger(phase="check")
        logger.started()

        files = list(runs.glob("*.jsonl"))
        event = json.loads(files[0].read_text().strip())
        assert event["tishift_version"] == "0.1.0"

    def test_events_have_utc_timestamps(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        runs = tmp_path / "runs"
        monkeypatch.setattr("tishift.run_logger.RUNS_DIR", runs)
        logger = RunLogger(phase="scan")
        logger.started()

        files = list(runs.glob("*.jsonl"))
        event = json.loads(files[0].read_text().strip())
        assert event["timestamp"].endswith("Z")


# ---------------------------------------------------------------------------
# summarize_report
# ---------------------------------------------------------------------------


class TestSummarizeReport:
    def _make_report(self) -> ScanReport:
        inventory = SchemaInventory(
            tables=[
                TableInfo("db", "t1", "InnoDB", "Dynamic", 100, 1024, 512, 1, "utf8mb4_general_ci", None),
                TableInfo("db", "t2", "InnoDB", "Dynamic", 200, 2048, 1024, 1, "utf8mb4_general_ci", None),
            ],
        )
        assessment = AssessmentResult(
            blockers=[Issue(type="spatial_gis", object_name="t1.geom", severity=Severity.BLOCKER, message="unsupported")],
            warnings=[Issue(type="stored_procedure", object_name="sp1", severity=Severity.WARNING, message="no exec")],
            info=[],
        )
        scoring = ScoringResult(
            schema_compatibility=CategoryScore("Schema Compat", 7, 10),
            data_complexity=CategoryScore("Data Complexity", 20, 20),
            query_compatibility=CategoryScore("Query Compat", 18, 20),
            procedural_code=CategoryScore("Procedural Code", 8, 20),
            operational_readiness=CategoryScore("Operational", 10, 10),
        )
        return ScanReport(
            source_host="mydb.cluster-abc.us-east-1.rds.amazonaws.com",
            database="mydb",
            schema_inventory=inventory,
            assessment=assessment,
            scoring=scoring,
            automation=AutomationCoverage(fully_automated_pct=60.0, ai_assisted_pct=14.3),
        )

    def test_no_real_hostname(self) -> None:
        report = self._make_report()
        summary = summarize_report(report)
        assert summary["source_type"] == "aws-aurora"
        assert "cluster" not in json.dumps(summary)

    def test_no_real_database_name(self) -> None:
        report = self._make_report()
        summary = summarize_report(report)
        assert summary["database_fingerprint"] == fingerprint("mydb")
        assert "mydb" not in json.dumps(summary).replace(fingerprint("mydb"), "")

    def test_contains_numeric_metrics(self) -> None:
        report = self._make_report()
        summary = summarize_report(report)
        assert summary["table_count"] == 2
        assert summary["overall_score"] == 63
        assert summary["rating"] == "moderate"
        assert summary["blocker_count"] == 1
        assert summary["warning_count"] == 1
        assert summary["blocker_types"] == ["spatial_gis"]
        assert summary["automation_pct"] == 74.3
