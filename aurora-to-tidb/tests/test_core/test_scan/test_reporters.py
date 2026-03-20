"""Tests for scan reporters: JSON and HTML."""

from __future__ import annotations

import json

import pytest

from tishift.core.scan.analyzers.automation import compute_automation
from tishift.core.scan.analyzers.compatibility import assess_compatibility
from tishift.core.scan.analyzers.scoring import compute_scores
from tishift.core.scan.reporters.html_report import generate_html_report
from tishift.core.scan.reporters.json_report import generate_json_report, to_json_string
from tishift.models import (
    CostAnalysis,
    CostBreakdown,
    ScanReport,
    SPAIAnalysis,
    SPComplexity,
    SPDifficulty,
    TiDBRecommendation,
)


@pytest.fixture
def sample_report(sample_inventory, sample_data_profile, sample_aurora_metadata):
    report = ScanReport(
        source_host="aurora-test.example.com",
        database="tishift_test",
        schema_inventory=sample_inventory,
        data_profile=sample_data_profile,
        aurora_metadata=sample_aurora_metadata,
    )
    report.assessment = assess_compatibility(sample_inventory)
    report.scoring = compute_scores(
        sample_inventory, sample_data_profile, sample_aurora_metadata
    )
    report.automation = compute_automation(sample_inventory)
    report.sp_analysis = [
        SPAIAnalysis(
            routine_schema="tishift_test",
            routine_name="get_customer_orders",
            routine_type="PROCEDURE",
            complexity=SPComplexity(
                loc=10,
                cursor_count=0,
                dynamic_sql_count=0,
                temp_table_count=0,
                control_flow_count=1,
                nested_calls=0,
                transaction_statements=0,
            ),
            difficulty=SPDifficulty.SIMPLE,
            automation_pct=90,
            summary="Fetches customer orders",
            suggested_approach="Move to application layer",
        )
    ]
    report.cost_analysis = CostAnalysis(
        aurora_monthly_estimate=1200.0,
        tidb_monthly_estimate=900.0,
        savings_pct=25.0,
        aurora_breakdown=CostBreakdown(compute=800.0, storage=300.0, io=100.0),
        tidb_recommendation=TiDBRecommendation(
            tier="Essential",
            nodes=2,
            vcpu=4,
            ram_gb=16,
            storage_gb=200,
            monthly_estimate=900.0,
        ),
    )
    return report


class TestJSONReport:
    def test_has_required_top_level_keys(self, sample_report):
        data = generate_json_report(sample_report)
        assert "version" in data
        assert "generated_at" in data
        assert "source" in data
        assert "summary" in data
        assert "scores" in data
        assert "issues" in data
        assert "schema_details" in data
        assert "data_profile" in data
        assert "sp_analysis" in data
        assert "cost_analysis" in data

    def test_summary_has_score(self, sample_report):
        data = generate_json_report(sample_report)
        assert 0 <= data["summary"]["overall_score"] <= 100
        assert data["summary"]["rating"] in ("excellent", "good", "moderate", "challenging", "difficult")

    def test_scores_has_five_categories(self, sample_report):
        data = generate_json_report(sample_report)
        assert len(data["scores"]) == 5
        for cat in data["scores"].values():
            assert "score" in cat
            assert "max" in cat

    def test_json_string_is_valid(self, sample_report):
        s = to_json_string(sample_report)
        parsed = json.loads(s)
        assert parsed["version"] == "1.0.0"

    def test_schema_details_has_tables(self, sample_report):
        data = generate_json_report(sample_report)
        assert len(data["schema_details"]["tables"]) == 3

    def test_issues_structure(self, sample_report):
        data = generate_json_report(sample_report)
        assert isinstance(data["issues"]["blockers"], list)
        assert isinstance(data["issues"]["warnings"], list)
        assert isinstance(data["issues"]["info"], list)


class TestHTMLReport:
    def test_renders_html(self, sample_report):
        html = generate_html_report(sample_report)
        assert "<!DOCTYPE html>" in html
        assert "TiShift" in html

    def test_contains_score(self, sample_report):
        html = generate_html_report(sample_report)
        score = sample_report.scoring.overall_score
        assert f"{score}/100" in html

    def test_contains_table_data(self, sample_report):
        html = generate_html_report(sample_report)
        assert "customers" in html
        assert "orders" in html

    def test_self_contained_css(self, sample_report):
        html = generate_html_report(sample_report)
        assert "<style>" in html
        # No external stylesheet references.
        assert 'rel="stylesheet"' not in html
