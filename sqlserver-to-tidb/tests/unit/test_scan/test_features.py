"""Tests for feature collector — regex patterns: true positives and no false positives."""

from __future__ import annotations

from tishift_mssql.models import RoutineInfo, SchemaInventory, TriggerInfo, ViewInfo
from tishift_mssql.scan.collectors.features import collect_features


class TestTruePositives:
    def test_detects_merge(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", "MERGE INTO target USING source ON ...", False, None),
        ])
        result = collect_features(inv)
        assert any(u.pattern_name == "merge" for u in result.usages)

    def test_detects_for_xml(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", "SELECT * FOR XML PATH('')", False, None),
        ])
        result = collect_features(inv)
        assert any(u.pattern_name == "for_xml" for u in result.usages)

    def test_detects_cross_apply(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", "SELECT * FROM t CROSS APPLY fn(t.id)", False, None),
        ])
        result = collect_features(inv)
        assert any(u.pattern_name == "cross_apply" for u in result.usages)

    def test_detects_outer_apply(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", "SELECT * FROM t OUTER APPLY fn(t.id)", False, None),
        ])
        result = collect_features(inv)
        assert any(u.pattern_name == "outer_apply" for u in result.usages)

    def test_detects_pivot(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", "SELECT * FROM t PIVOT (SUM(v) FOR c IN ([a],[b]))", False, None),
        ])
        result = collect_features(inv)
        assert any(u.pattern_name == "pivot" for u in result.usages)

    def test_detects_cursor(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", "DECLARE c CURSOR FOR SELECT 1", False, None),
        ])
        result = collect_features(inv)
        assert any(u.pattern_name == "cursor" for u in result.usages)

    def test_detects_sp_executesql(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", "EXEC sp_executesql @sql", False, None),
        ])
        result = collect_features(inv)
        assert any(u.pattern_name == "sp_executesql" for u in result.usages)

    def test_detects_nolock(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", "SELECT * FROM t WITH (NOLOCK)", False, None),
        ])
        result = collect_features(inv)
        assert any(u.pattern_name == "nolock" for u in result.usages)

    def test_detects_openquery(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", "SELECT * FROM OPENQUERY(SRV, 'SELECT 1')", False, None),
        ])
        result = collect_features(inv)
        assert any(u.pattern_name == "openquery" for u in result.usages)

    def test_detects_try_catch(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", "BEGIN TRY SELECT 1 END TRY BEGIN CATCH END CATCH", False, None),
        ])
        result = collect_features(inv)
        assert any(u.pattern_name == "try_catch" for u in result.usages)

    def test_detects_temp_table(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", "SELECT * INTO #tmp FROM t", False, None),
        ])
        result = collect_features(inv)
        assert any(u.pattern_name == "temp_table" for u in result.usages)

    def test_detects_service_broker(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", "BEGIN DIALOG @handle", False, None),
        ])
        result = collect_features(inv)
        assert any(u.pattern_name == "service_broker" for u in result.usages)


class TestFalsePositives:
    def test_plain_select_no_matches(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", "SELECT id, name FROM customers WHERE id = 1", False, None),
        ])
        result = collect_features(inv)
        assert len(result.usages) == 0

    def test_empty_definition_no_crash(self) -> None:
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", None, False, None),
        ])
        result = collect_features(inv)
        assert len(result.usages) == 0


class TestMultipleMatches:
    def test_counts_all_occurrences(self) -> None:
        definition = "SELECT * FROM t WITH (NOLOCK) UNION ALL SELECT * FROM u WITH (NOLOCK)"
        inv = SchemaInventory(routines=[
            RoutineInfo("dbo", "sp", "SQL_STORED_PROCEDURE", definition, False, None),
        ])
        result = collect_features(inv)
        nolock_matches = [u for u in result.usages if u.pattern_name == "nolock"]
        assert len(nolock_matches) == 2


class TestTriggersAndViews:
    def test_scans_trigger_definitions(self) -> None:
        inv = SchemaInventory(triggers=[
            TriggerInfo("dbo", "trg", "t", False, False, "SELECT * FOR XML PATH('')"),
        ])
        result = collect_features(inv)
        assert any(u.pattern_name == "for_xml" for u in result.usages)

    def test_scans_view_definitions(self) -> None:
        inv = SchemaInventory(views=[
            ViewInfo("dbo", "v", "SELECT * FROM t CROSS APPLY fn(t.id)", False, False),
        ])
        result = collect_features(inv)
        assert any(u.pattern_name == "cross_apply" for u in result.usages)
