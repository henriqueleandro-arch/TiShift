"""Tests for compatibility analyzer — each blocker/warning type."""

from __future__ import annotations

from tishift_mssql.models import (
    AssemblyInfo,
    ColumnInfo,
    FeatureScanResult,
    FeatureUsage,
    IndexInfo,
    LinkedServerInfo,
    AgentJobInfo,
    RoutineInfo,
    SchemaInventory,
    SQLServerMetadata,
    Severity,
    TableInfo,
    TriggerInfo,
)
from tishift_mssql.scan.analyzers.compatibility import assess_compatibility


def _meta(**overrides) -> SQLServerMetadata:
    defaults = dict(
        version="Microsoft SQL Server 2022",
        edition="Enterprise Edition",
        db_collation="SQL_Latin1_General_CP1_CI_AS",
        cdc_enabled=True,
    )
    defaults.update(overrides)
    return SQLServerMetadata(**defaults)


def _empty_features() -> FeatureScanResult:
    return FeatureScanResult()


class TestBlockers:
    def test_stored_procedure_flagged(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp_test", "SQL_STORED_PROCEDURE", "CREATE PROC sp_test AS SELECT 1", False, None),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "stored_procedure" and i.severity == Severity.BLOCKER for i in result.blockers)

    def test_clr_routine_flagged(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "clr_func", "CLR_SCALAR_FUNCTION", None, True, "MyAssembly"),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "clr" for i in result.blockers)

    def test_clr_assembly_flagged(self) -> None:
        inv = SchemaInventory(assemblies=[AssemblyInfo("Utils", "SAFE", "Utils.dll")])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "clr" for i in result.blockers)

    def test_trigger_flagged(self) -> None:
        inv = SchemaInventory(triggers=[
            TriggerInfo("dbo", "trg_test", "orders", False, False, "CREATE TRIGGER ..."),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "trigger" and i.severity == Severity.BLOCKER for i in result.blockers)

    def test_linked_server_flagged(self) -> None:
        inv = SchemaInventory(linked_servers=[
            LinkedServerInfo("REMOTE", "SQL Server", "SQLOLEDB", "srv"),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "linked_server" for i in result.blockers)

    def test_hierarchyid_flagged(self) -> None:
        inv = SchemaInventory(columns=[
            ColumnInfo("dbo", "t", "path", 1, "hierarchyid", 892, None, None, True, False, False, None, None, None),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "spatial" for i in result.blockers)

    def test_spatial_columns_flagged(self) -> None:
        inv = SchemaInventory(columns=[
            ColumnInfo("dbo", "t", "loc", 1, "geography", -1, None, None, True, False, False, None, None, None),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "spatial" for i in result.blockers)

    def test_xml_type_flagged(self) -> None:
        inv = SchemaInventory(columns=[
            ColumnInfo("dbo", "t", "data", 1, "xml", -1, None, None, True, False, False, None, None, None),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "xml_type" for i in result.blockers)

    def test_sql_variant_flagged(self) -> None:
        inv = SchemaInventory(columns=[
            ColumnInfo("dbo", "t", "val", 1, "sql_variant", -1, None, None, True, False, False, None, None, None),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "sql_variant" for i in result.blockers)

    def test_merge_from_features_flagged(self) -> None:
        inv = SchemaInventory()
        features = FeatureScanResult(usages=[
            FeatureUsage("merge", "routine", "dbo.sp_test", "MERGE INTO"),
        ])
        result = assess_compatibility(inv, features, _meta())
        assert any(i.type == "merge" for i in result.blockers)


class TestWarnings:
    def test_identity_column_warned(self) -> None:
        inv = SchemaInventory(columns=[
            ColumnInfo("dbo", "t", "id", 1, "int", 4, 10, 0, False, True, False, None, None, None),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "identity" for i in result.warnings)

    def test_computed_column_warned(self) -> None:
        inv = SchemaInventory(columns=[
            ColumnInfo("dbo", "t", "full_name", 2, "nvarchar", 500, None, None, True, False, True, None, "[first] + ' ' + [last]", None),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "computed_column" for i in result.warnings)

    def test_filtered_index_warned(self) -> None:
        inv = SchemaInventory(indexes=[
            IndexInfo("dbo", "t", "ix_filt", "NONCLUSTERED", False, False, "col", "", "col = 1"),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "filtered_index" for i in result.warnings)

    def test_columnstore_index_warned(self) -> None:
        inv = SchemaInventory(indexes=[
            IndexInfo("dbo", "t", "ix_cs", "CLUSTERED COLUMNSTORE", False, False, "", "", None),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "columnstore" for i in result.warnings)

    def test_memory_optimized_warned(self) -> None:
        inv = SchemaInventory(tables=[
            TableInfo("dbo", "mem_t", 10, 1.0, 0.5, True, False, False),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "memory_optimized" for i in result.warnings)

    def test_temporal_warned(self) -> None:
        inv = SchemaInventory(tables=[
            TableInfo("dbo", "hist_t", 10, 1.0, 0.5, False, True, False),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "temporal" for i in result.warnings)

    def test_instead_of_trigger_warned(self) -> None:
        inv = SchemaInventory(triggers=[
            TriggerInfo("dbo", "trg_io", "t", True, False, "CREATE TRIGGER trg_io INSTEAD OF INSERT ..."),
        ])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "instead_of_trigger" for i in result.warnings)

    def test_agent_job_warned(self) -> None:
        inv = SchemaInventory(agent_jobs=[AgentJobInfo("job1", True, "desc")])
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert any(i.type == "agent_job" for i in result.warnings)

    def test_collation_mismatch_warned(self) -> None:
        inv = SchemaInventory()
        result = assess_compatibility(inv, _empty_features(), _meta(db_collation="Latin1_General_100_CI_AS"))
        assert any(i.type == "collation" for i in result.warnings)


class TestCleanDatabase:
    def test_clean_db_has_no_blockers(self) -> None:
        inv = SchemaInventory(
            tables=[TableInfo("dbo", "simple", 10, 1.0, 0.5, False, False, False)],
            columns=[
                ColumnInfo("dbo", "simple", "id", 1, "int", 4, 10, 0, False, False, False, None, None, None),
                ColumnInfo("dbo", "simple", "name", 2, "varchar", 100, None, None, True, False, False, None, None, None),
            ],
        )
        result = assess_compatibility(inv, _empty_features(), _meta())
        assert len(result.blockers) == 0
