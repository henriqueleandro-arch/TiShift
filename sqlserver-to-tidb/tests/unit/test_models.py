"""Tests for data models — immutability, enums, scoring properties."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from tishift_mssql.models import (
    CategoryScore,
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    Rating,
    ScoringResult,
    Severity,
    SPDifficulty,
    TableInfo,
    to_dict,
)


class TestFrozenDataclasses:
    def test_table_info_is_frozen(self) -> None:
        table = TableInfo("dbo", "t", 1, 1.0, 1.0, False, False, False)
        with pytest.raises(FrozenInstanceError):
            table.table_name = "x"  # type: ignore[misc]

    def test_column_info_is_frozen(self) -> None:
        col = ColumnInfo("dbo", "t", "c", 1, "int", 4, 10, 0, False, False, False, None, None, None)
        with pytest.raises(FrozenInstanceError):
            col.data_type = "bigint"  # type: ignore[misc]

    def test_index_info_is_frozen(self) -> None:
        idx = IndexInfo("dbo", "t", "ix", "NONCLUSTERED", False, False, "col", "", None)
        with pytest.raises(FrozenInstanceError):
            idx.is_unique = True  # type: ignore[misc]

    def test_foreign_key_info_is_frozen(self) -> None:
        fk = ForeignKeyInfo("dbo", "t", "fk", "dbo", "ref", "col", "ref_col", "NO_ACTION", "NO_ACTION")
        with pytest.raises(FrozenInstanceError):
            fk.fk_name = "other"  # type: ignore[misc]

    def test_category_score_is_frozen(self) -> None:
        score = CategoryScore("test", 20, 25, [])
        with pytest.raises(FrozenInstanceError):
            score.score = 10  # type: ignore[misc]


class TestEnums:
    def test_severity_values(self) -> None:
        assert Severity.BLOCKER.value == "blocker"
        assert Severity.WARNING.value == "warning"
        assert Severity.INFO.value == "info"

    def test_rating_values(self) -> None:
        assert Rating.EXCELLENT.value == "excellent"
        assert Rating.DIFFICULT.value == "difficult"

    def test_sp_difficulty_values(self) -> None:
        assert SPDifficulty.TRIVIAL.value == "trivial"
        assert SPDifficulty.REQUIRES_REDESIGN.value == "requires_redesign"


class TestScoringResult:
    def test_overall_score_zero_when_empty(self) -> None:
        scoring = ScoringResult()
        assert scoring.overall_score == 0

    def test_rating_difficult_for_zero(self) -> None:
        scoring = ScoringResult()
        assert scoring.rating == Rating.DIFFICULT

    def test_rating_excellent_for_high_scores(self) -> None:
        scoring = ScoringResult(
            schema_compatibility=CategoryScore("s", 25, 25),
            code_portability=CategoryScore("c", 25, 25),
            query_compatibility=CategoryScore("q", 20, 20),
            data_complexity=CategoryScore("d", 20, 20),
            operational_readiness=CategoryScore("o", 10, 10),
        )
        assert scoring.overall_score == 100
        assert scoring.rating == Rating.EXCELLENT

    def test_rating_good_for_70_84(self) -> None:
        scoring = ScoringResult(
            schema_compatibility=CategoryScore("s", 20, 25),
            code_portability=CategoryScore("c", 18, 25),
            query_compatibility=CategoryScore("q", 15, 20),
            data_complexity=CategoryScore("d", 14, 20),
            operational_readiness=CategoryScore("o", 8, 10),
        )
        assert 70 <= scoring.overall_score <= 84
        assert scoring.rating == Rating.GOOD

    def test_rating_moderate_for_50_69(self) -> None:
        scoring = ScoringResult(
            schema_compatibility=CategoryScore("s", 15, 25),
            code_portability=CategoryScore("c", 10, 25),
            query_compatibility=CategoryScore("q", 12, 20),
            data_complexity=CategoryScore("d", 10, 20),
            operational_readiness=CategoryScore("o", 5, 10),
        )
        assert 50 <= scoring.overall_score <= 69
        assert scoring.rating == Rating.MODERATE

    def test_rating_challenging_for_25_49(self) -> None:
        scoring = ScoringResult(
            schema_compatibility=CategoryScore("s", 8, 25),
            code_portability=CategoryScore("c", 5, 25),
            query_compatibility=CategoryScore("q", 8, 20),
            data_complexity=CategoryScore("d", 7, 20),
            operational_readiness=CategoryScore("o", 2, 10),
        )
        assert 25 <= scoring.overall_score <= 49
        assert scoring.rating == Rating.CHALLENGING


class TestToDict:
    def test_serializes_enums(self) -> None:
        result = to_dict(Severity.BLOCKER)
        assert result == "blocker"

    def test_serializes_nested_dataclass(self) -> None:
        table = TableInfo("dbo", "t", 1, 1.0, 0.5, False, False, True)
        d = to_dict(table)
        assert d["schema_name"] == "dbo"
        assert d["is_heap"] is True

    def test_serializes_list(self) -> None:
        result = to_dict([Severity.BLOCKER, Severity.WARNING])
        assert result == ["blocker", "warning"]
