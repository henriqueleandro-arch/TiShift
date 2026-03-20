"""Tests for scoring engine — deductions, floor at 0, rating thresholds."""

from __future__ import annotations

from tishift_mssql.models import (
    ColumnInfo,
    DataProfile,
    FeatureScanResult,
    QueryPatterns,
    QueryIssue,
    Rating,
    SchemaInventory,
    Severity,
    SQLServerMetadata,
    TableInfo,
    TableSize,
)
from tishift_mssql.scan.analyzers.scoring import compute_scores


def _meta(**overrides) -> SQLServerMetadata:
    defaults = dict(
        version="Microsoft SQL Server 2022",
        edition="Enterprise Edition",
        product_version="16.0.4135.4",
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        cdc_enabled=True,
        auth_mode="sql",
    )
    defaults.update(overrides)
    return SQLServerMetadata(**defaults)


class TestOverallBounds:
    def test_score_is_between_0_and_100(self, sample_inventory, sample_metadata) -> None:
        scores = compute_scores(sample_inventory, DataProfile(), sample_metadata, FeatureScanResult())
        assert 0 <= scores.overall_score <= 100

    def test_perfect_score_for_empty_db(self) -> None:
        inv = SchemaInventory(schemas=["dbo"])
        meta = _meta()
        scores = compute_scores(inv, DataProfile(), meta, FeatureScanResult())
        # No SPs, no triggers, no special types, CDC enabled → should be close to max
        # Query compatibility defaults to 16/20 when no query log
        assert scores.overall_score >= 85

    def test_floor_at_zero_for_code_portability(self, sample_inventory_complex, sample_metadata) -> None:
        scores = compute_scores(sample_inventory_complex, DataProfile(), sample_metadata, FeatureScanResult())
        assert scores.code_portability is not None
        assert scores.code_portability.score >= 0


class TestSchemaCompatibility:
    def test_deprecated_types_deduction(self) -> None:
        inv = SchemaInventory(
            columns=[
                ColumnInfo("dbo", "t", "pic", 1, "image", -1, None, None, True, False, False, None, None, None),
                ColumnInfo("dbo", "t", "desc", 2, "ntext", -1, None, None, True, False, False, None, None, None),
            ],
            schemas=["dbo"],
        )
        scores = compute_scores(inv, DataProfile(), _meta(), FeatureScanResult())
        assert scores.schema_compatibility is not None
        assert any("deprecated" in d.lower() or "IMAGE" in d for d in scores.schema_compatibility.deductions)

    def test_hierarchyid_deduction(self) -> None:
        inv = SchemaInventory(
            columns=[ColumnInfo("dbo", "t", "path", 1, "hierarchyid", 892, None, None, True, False, False, None, None, None)],
            schemas=["dbo"],
        )
        scores = compute_scores(inv, DataProfile(), _meta(), FeatureScanResult())
        assert scores.schema_compatibility is not None
        assert scores.schema_compatibility.score < 25

    def test_temporal_tables_deduction(self) -> None:
        inv = SchemaInventory(
            tables=[TableInfo("dbo", "t", 10, 1.0, 0.5, False, True, False)],
            schemas=["dbo"],
        )
        scores = compute_scores(inv, DataProfile(), _meta(), FeatureScanResult())
        assert scores.schema_compatibility is not None
        assert any("Temporal" in d for d in scores.schema_compatibility.deductions)

    def test_non_dbo_schemas_deduction(self) -> None:
        inv = SchemaInventory(schemas=["dbo", "sales", "hr"])
        scores = compute_scores(inv, DataProfile(), _meta(), FeatureScanResult())
        assert scores.schema_compatibility is not None
        assert any("non-dbo" in d for d in scores.schema_compatibility.deductions)


class TestCodePortability:
    def test_no_code_gets_full_score(self) -> None:
        inv = SchemaInventory(schemas=["dbo"])
        scores = compute_scores(inv, DataProfile(), _meta(), FeatureScanResult())
        assert scores.code_portability is not None
        assert scores.code_portability.score == 25

    def test_ssis_deduction(self) -> None:
        inv = SchemaInventory(schemas=["dbo"])
        meta = _meta(has_ssis=True)
        scores = compute_scores(inv, DataProfile(), meta, FeatureScanResult())
        assert scores.code_portability is not None
        assert any("SSIS" in d for d in scores.code_portability.deductions)


class TestQueryCompatibility:
    def test_defaults_to_16_when_no_query_log(self) -> None:
        inv = SchemaInventory(schemas=["dbo"])
        scores = compute_scores(inv, DataProfile(), _meta(), FeatureScanResult())
        assert scores.query_compatibility is not None
        assert scores.query_compatibility.score == 16

    def test_merge_in_queries_deducts(self) -> None:
        inv = SchemaInventory(schemas=["dbo"])
        qp = QueryPatterns(total_queries_analyzed=10, issues=[
            QueryIssue("MERGE INTO t ...", "merge", Severity.BLOCKER, "merge", False),
            QueryIssue("MERGE INTO u ...", "merge", Severity.BLOCKER, "merge", False),
        ])
        scores = compute_scores(inv, DataProfile(), _meta(), FeatureScanResult(), qp)
        assert scores.query_compatibility is not None
        assert scores.query_compatibility.score < 20


class TestDataComplexity:
    def test_small_data_full_score(self) -> None:
        inv = SchemaInventory(schemas=["dbo"])
        profile = DataProfile(total_data_mb=100.0)
        scores = compute_scores(inv, profile, _meta(), FeatureScanResult())
        assert scores.data_complexity is not None
        assert scores.data_complexity.score == 20

    def test_large_data_deduction(self, large_data_profile) -> None:
        inv = SchemaInventory(schemas=["dbo"])
        scores = compute_scores(inv, large_data_profile, _meta(), FeatureScanResult())
        assert scores.data_complexity is not None
        assert scores.data_complexity.score < 15

    def test_money_columns_deduction(self) -> None:
        inv = SchemaInventory(
            columns=[ColumnInfo("dbo", "t", "price", 1, "money", 8, 19, 4, False, False, False, None, None, None)],
            schemas=["dbo"],
        )
        scores = compute_scores(inv, DataProfile(), _meta(), FeatureScanResult())
        assert scores.data_complexity is not None
        assert any("MONEY" in d for d in scores.data_complexity.deductions)


class TestOperationalReadiness:
    def test_cdc_not_enabled_deduction(self) -> None:
        inv = SchemaInventory(schemas=["dbo"])
        meta = _meta(cdc_enabled=False)
        scores = compute_scores(inv, DataProfile(), meta, FeatureScanResult(), tier="dedicated")
        assert scores.operational_readiness is not None
        assert any("CDC" in d for d in scores.operational_readiness.deductions)

    def test_starter_tier_cutover_deduction(self) -> None:
        inv = SchemaInventory(schemas=["dbo"])
        meta = _meta(cdc_enabled=False)
        scores = compute_scores(inv, DataProfile(), meta, FeatureScanResult(), tier="starter")
        assert scores.operational_readiness is not None
        assert any("cutover" in d.lower() for d in scores.operational_readiness.deductions)

    def test_old_version_deduction(self) -> None:
        inv = SchemaInventory(schemas=["dbo"])
        meta = _meta(product_version="12.0.6024.0")  # SQL Server 2014
        scores = compute_scores(inv, DataProfile(), meta, FeatureScanResult())
        assert scores.operational_readiness is not None
        assert any("2016" in d for d in scores.operational_readiness.deductions)

    def test_windows_auth_deduction(self) -> None:
        inv = SchemaInventory(schemas=["dbo"])
        meta = _meta(auth_mode="windows")
        scores = compute_scores(inv, DataProfile(), meta, FeatureScanResult())
        assert scores.operational_readiness is not None
        assert any("Windows" in d or "auth" in d.lower() for d in scores.operational_readiness.deductions)
