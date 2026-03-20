"""Tests for JSON report generation — structure validation."""

from __future__ import annotations

import json

from tishift_mssql.models import (
    AssessmentResult,
    AutomationCoverage,
    CategoryScore,
    CostEstimate,
    DataProfile,
    FeatureScanResult,
    Issue,
    ScanReport,
    SchemaInventory,
    Severity,
    ScoringResult,
    SQLServerMetadata,
    TableInfo,
)
from tishift_mssql.scan.reporters.json_report import generate_json_report


class TestJsonReport:
    def test_basic_structure(self, tmp_path) -> None:
        output = tmp_path / "report.json"
        generate_json_report(ScanReport(source_host="srv", database="db1"), output)
        payload = json.loads(output.read_text())
        assert payload["source_host"] == "srv"
        assert payload["database"] == "db1"
        assert "version" in payload
        assert "generated_at" in payload

    def test_contains_scoring(self, tmp_path) -> None:
        report = ScanReport(
            scoring=ScoringResult(
                schema_compatibility=CategoryScore("Schema Compatibility", 21, 25, ["2 deprecated cols"]),
                code_portability=CategoryScore("Code Portability", 15, 25),
                query_compatibility=CategoryScore("Query Compatibility", 16, 20),
                data_complexity=CategoryScore("Data Complexity", 18, 20),
                operational_readiness=CategoryScore("Operational Readiness", 8, 10),
            )
        )
        output = tmp_path / "report.json"
        generate_json_report(report, output)
        payload = json.loads(output.read_text())
        scoring = payload["scoring"]
        assert scoring["schema_compatibility"]["score"] == 21
        assert scoring["code_portability"]["score"] == 15

    def test_contains_assessment(self, tmp_path) -> None:
        report = ScanReport(
            assessment=AssessmentResult(
                blockers=[Issue("stored_procedure", "dbo.sp", Severity.BLOCKER, "not supported")],
                warnings=[Issue("identity", "dbo.t.id", Severity.WARNING, "differs")],
            )
        )
        output = tmp_path / "report.json"
        generate_json_report(report, output)
        payload = json.loads(output.read_text())
        assert len(payload["assessment"]["blockers"]) == 1
        assert payload["assessment"]["blockers"][0]["severity"] == "blocker"

    def test_contains_inventory(self, tmp_path) -> None:
        report = ScanReport(
            schema_inventory=SchemaInventory(
                tables=[TableInfo("dbo", "t", 100, 1.0, 0.5, False, False, False)],
            )
        )
        output = tmp_path / "report.json"
        generate_json_report(report, output)
        payload = json.loads(output.read_text())
        assert len(payload["schema_inventory"]["tables"]) == 1

    def test_contains_cost_estimate(self, tmp_path) -> None:
        report = ScanReport(
            cost_estimate=CostEstimate(
                estimated_monthly_sqlserver_license_usd=8420.0,
                assumptions=["Enterprise", "16 cores"],
            )
        )
        output = tmp_path / "report.json"
        generate_json_report(report, output)
        payload = json.loads(output.read_text())
        assert payload["cost_estimate"]["estimated_monthly_sqlserver_license_usd"] == 8420.0

    def test_roundtrip_serializable(self, tmp_path) -> None:
        """Ensure the full report serializes without errors."""
        report = ScanReport(
            source_host="test-srv",
            database="testdb",
            schema_inventory=SchemaInventory(
                tables=[TableInfo("dbo", "t", 10, 1.0, 0.5, False, False, False)],
            ),
            data_profile=DataProfile(total_data_mb=1.0, total_rows=10),
            sqlserver_metadata=SQLServerMetadata(version="2022", edition="Enterprise"),
            feature_scan=FeatureScanResult(),
            assessment=AssessmentResult(),
            scoring=ScoringResult(
                schema_compatibility=CategoryScore("s", 25, 25),
            ),
            automation=AutomationCoverage(fully_automated_pct=80.0, ai_assisted_pct=15.0, manual_required_pct=5.0),
        )
        output = tmp_path / "report.json"
        generate_json_report(report, output)
        payload = json.loads(output.read_text())
        # Should round-trip cleanly
        json.dumps(payload)
