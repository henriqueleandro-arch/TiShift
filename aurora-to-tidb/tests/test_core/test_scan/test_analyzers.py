"""Tests for scan analyzers: compatibility, scoring, and automation."""

from __future__ import annotations

import pytest

from tishift.core.scan.analyzers.automation import compute_automation
from tishift.core.scan.analyzers.compatibility import assess_compatibility
from tishift.core.scan.analyzers.scoring import (
    _classify_sp_difficulty,
    compute_scores,
    score_data_complexity,
    score_operational_readiness,
    score_procedural_code,
    score_query_compatibility,
    score_schema_compatibility,
)
from tishift.models import (
    AuroraMetadata,
    ColumnInfo,
    DataProfile,
    EventInfo,
    IndexInfo,
    QueryIssue,
    QueryPatterns,
    SchemaInventory,
    Severity,
    SPDifficulty,
    TableSize,
)


# ── Compatibility Assessment ──


class TestAssessCompatibility:
    def test_flags_stored_procedures(self, sample_inventory):
        result = assess_compatibility(sample_inventory)
        sp_warnings = [i for i in result.warnings if i.type == "stored_procedure"]
        assert len(sp_warnings) == 1
        assert "get_customer_orders" in sp_warnings[0].object_name

    def test_flags_triggers(self, sample_inventory):
        result = assess_compatibility(sample_inventory)
        trg_warnings = [i for i in result.warnings if i.type == "trigger"]
        assert len(trg_warnings) == 1
        assert "after_order_insert" in trg_warnings[0].object_name

    def test_flags_foreign_keys_as_info(self, sample_inventory):
        result = assess_compatibility(sample_inventory)
        fk_info = [i for i in result.info if i.type == "foreign_key"]
        assert len(fk_info) == 1

    def test_flags_spatial_columns_as_blocker(self, sample_inventory):
        sample_inventory.columns = list(sample_inventory.columns) + [
            ColumnInfo("db", "t", "location", 1, None, "YES", "point", "point",
                       None, None, "", "", None)
        ]
        result = assess_compatibility(sample_inventory)
        assert len(result.blockers) == 1
        assert result.blockers[0].type == "spatial_gis"

    def test_flags_fulltext_indexes(self, sample_inventory):
        sample_inventory.indexes = list(sample_inventory.indexes) + [
            IndexInfo("db", "t", "ft_idx", 1, "FULLTEXT", "col")
        ]
        result = assess_compatibility(sample_inventory)
        ft_warnings = [i for i in result.warnings if i.type == "fulltext_index"]
        assert len(ft_warnings) == 1

    def test_flags_events(self, sample_inventory):
        sample_inventory.events = [
            EventInfo("db", "daily_cleanup", "RECURRING", None, "1", "DAY",
                      "DELETE FROM logs WHERE created_at < NOW() - INTERVAL 30 DAY", "ENABLED")
        ]
        result = assess_compatibility(sample_inventory)
        evt_warnings = [i for i in result.warnings if i.type == "event"]
        assert len(evt_warnings) == 1

    def test_no_blockers_for_clean_schema(self, sample_inventory):
        result = assess_compatibility(sample_inventory)
        assert len(result.blockers) == 0


# ── SP Difficulty Classifier ──


class TestSPDifficulty:
    def test_trivial(self):
        sp = "BEGIN\n  SELECT 1;\nEND"
        assert _classify_sp_difficulty(sp) == SPDifficulty.TRIVIAL

    def test_simple(self):
        sp = "\n".join([f"  SELECT col{i} FROM t{i};" for i in range(15)])
        assert _classify_sp_difficulty(sp) == SPDifficulty.SIMPLE

    def test_moderate_with_cursor(self):
        sp = "BEGIN\n  DECLARE cur CURSOR FOR SELECT id FROM t;\n" + "\n".join(
            [f"  SELECT {i};" for i in range(50)]
        ) + "\nEND"
        assert _classify_sp_difficulty(sp) == SPDifficulty.MODERATE

    def test_complex_with_dynamic_sql(self):
        sp = "BEGIN\n  PREPARE stmt FROM @sql;\n  EXECUTE stmt;\n" + "\n".join(
            [f"  SELECT {i};" for i in range(20)]
        ) + "\nEND"
        assert _classify_sp_difficulty(sp) == SPDifficulty.COMPLEX

    def test_none_definition(self):
        assert _classify_sp_difficulty(None) == SPDifficulty.SIMPLE


# ── Scoring Engine ──


class TestSchemaCompatibilityScore:
    def test_clean_schema_gets_high_score(self):
        inv = SchemaInventory()
        inv.tables = []
        result = score_schema_compatibility(inv)
        assert result.score == 30

    def test_sp_deduction(self, sample_inventory):
        result = score_schema_compatibility(sample_inventory)
        # 1 SP = -2, 1 trigger = -2, 1 FK = -1, 1 unsupported collation (utf8mb4_0900_ai_ci) = -1
        assert result.score <= 30

    def test_deductions_capped(self, sample_inventory):
        result = score_schema_compatibility(sample_inventory)
        assert result.score >= 0


class TestDataComplexityScore:
    def test_small_data_full_score(self, sample_data_profile):
        result = score_data_complexity(sample_data_profile)
        assert result.score == 20

    def test_large_data_deduction(self):
        profile = DataProfile(
            table_sizes=[TableSize("db", "big", 1000000, 600000, 100000, 700000)],
            total_data_mb=600000.0,
            total_index_mb=100000.0,
            total_rows=1000000,
        )
        result = score_data_complexity(profile)
        assert result.score < 20


class TestQueryCompatibilityScore:
    def test_no_query_log_assumes_18(self):
        result = score_query_compatibility(None)
        assert result.score == 18

    def test_clean_queries_full_score(self):
        patterns = QueryPatterns(digests=[], issues=[], total_digests_analyzed=10)
        result = score_query_compatibility(patterns)
        assert result.score == 20

    def test_xa_deduction(self):
        patterns = QueryPatterns(
            digests=[],
            issues=[
                QueryIssue("XA START", "XA_TRANSACTION", Severity.BLOCKER,
                           "XA not supported", "Use standard transactions")
            ],
            total_digests_analyzed=1,
        )
        result = score_query_compatibility(patterns)
        assert result.score <= 18


class TestOperationalReadinessScore:
    def test_good_aurora_full_score(self, sample_aurora_metadata):
        result = score_operational_readiness(sample_aurora_metadata)
        assert result.score == 10

    def test_mixed_binlog_deduction(self):
        meta = AuroraMetadata(binlog_format="MIXED")
        result = score_operational_readiness(meta)
        assert result.score <= 5


class TestComputeScores:
    def test_overall_score(self, sample_inventory, sample_data_profile, sample_aurora_metadata):
        result = compute_scores(sample_inventory, sample_data_profile, sample_aurora_metadata)
        assert 0 <= result.overall_score <= 100
        assert result.rating is not None


# ── Automation Coverage ──


class TestAutomation:
    def test_tables_are_fully_automated(self, sample_inventory):
        coverage = compute_automation(sample_inventory)
        assert coverage.fully_automated_pct > 0

    def test_sp_adds_ai_assisted(self, sample_inventory):
        coverage = compute_automation(sample_inventory)
        assert coverage.ai_assisted_pct > 0

    def test_percentages_sum_to_100(self, sample_inventory):
        coverage = compute_automation(sample_inventory)
        total = (
            coverage.fully_automated_pct
            + coverage.ai_assisted_pct
            + coverage.manual_required_pct
        )
        assert abs(total - 100.0) < 1.0  # Allow rounding tolerance

    def test_empty_inventory(self):
        inv = SchemaInventory()
        coverage = compute_automation(inv)
        assert coverage.fully_automated_pct == 100.0
