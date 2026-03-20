"""Tests for automation coverage estimator."""

from __future__ import annotations

from tishift_mssql.models import (
    AssemblyInfo,
    AssessmentResult,
    FeatureScanResult,
    FeatureUsage,
    Issue,
    RoutineInfo,
    SchemaInventory,
    Severity,
    TableInfo,
    TriggerInfo,
)
from tishift_mssql.scan.analyzers.automation import compute_automation


class TestAutomationPercentages:
    def test_totals_to_100(self, sample_inventory, sample_feature_scan) -> None:
        assessment = AssessmentResult(blockers=[
            Issue("stored_procedure", "dbo.sp", Severity.BLOCKER, "x"),
        ])
        coverage = compute_automation(sample_inventory, sample_feature_scan, assessment)
        total = coverage.fully_automated_pct + coverage.ai_assisted_pct + coverage.manual_required_pct
        assert 99.9 <= total <= 100.1

    def test_clean_db_high_automation(self) -> None:
        inv = SchemaInventory(tables=[
            TableInfo("dbo", "t", 100, 1.0, 0.5, False, False, False),
        ])
        coverage = compute_automation(inv, FeatureScanResult(), AssessmentResult())
        assert coverage.fully_automated_pct >= 90.0
        assert coverage.manual_required_pct == 0.0

    def test_heavy_blockers_increases_manual(self) -> None:
        inv = SchemaInventory(
            tables=[TableInfo("dbo", "t", 10, 1.0, 0.5, False, False, False)],
            triggers=[TriggerInfo("dbo", f"trg_{i}", "t", False, False, "def") for i in range(10)],
            assemblies=[AssemblyInfo(f"asm_{i}", "SAFE", None) for i in range(5)],
        )
        blockers = [Issue("trigger", f"dbo.trg_{i}", Severity.BLOCKER, "x") for i in range(10)]
        assessment = AssessmentResult(blockers=blockers)
        coverage = compute_automation(inv, FeatureScanResult(), assessment)
        assert coverage.manual_required_pct > 30.0

    def test_includes_labels(self) -> None:
        inv = SchemaInventory(
            tables=[TableInfo("dbo", "t", 10, 1.0, 0.5, False, False, False)],
            routines=[RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", "def", False, None)],
            triggers=[TriggerInfo("dbo", "trg", "t", False, False, "def")],
            assemblies=[AssemblyInfo("asm", "SAFE", None)],
        )
        assessment = AssessmentResult()
        coverage = compute_automation(inv, FeatureScanResult(), assessment)
        assert any("DDL" in item or "Table" in item for item in coverage.fully_automated_includes)
        assert any("procedure" in item.lower() or "function" in item.lower() for item in coverage.ai_assisted_includes)
        assert any("Trigger" in item for item in coverage.manual_required_includes)
        assert any("CLR" in item for item in coverage.manual_required_includes)
