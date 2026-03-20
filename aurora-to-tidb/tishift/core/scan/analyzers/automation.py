"""Automation coverage calculator.

Estimates what percentage of the migration is fully automated,
AI-assisted, or requires manual work.
"""

from __future__ import annotations

import logging

from tishift.core.scan.analyzers.scoring import _classify_sp_difficulty
from tishift.models import (
    AutomationCoverage,
    SchemaInventory,
    SPAIAnalysis,
    SPDifficulty,
)

logger = logging.getLogger(__name__)

# Automation percentages per object type — from the spec table.
_SP_AUTOMATION: dict[SPDifficulty, tuple[float, float, float]] = {
    # (fully_auto, ai_assisted, manual)
    SPDifficulty.TRIVIAL: (0.0, 90.0, 10.0),
    SPDifficulty.SIMPLE: (0.0, 90.0, 10.0),
    SPDifficulty.MODERATE: (0.0, 70.0, 30.0),
    SPDifficulty.COMPLEX: (0.0, 50.0, 50.0),
    SPDifficulty.REQUIRES_REDESIGN: (0.0, 30.0, 70.0),
}


def compute_automation(
    inventory: SchemaInventory,
    ai_analysis: list[SPAIAnalysis] | None = None,
) -> AutomationCoverage:
    """Compute automation coverage from the schema inventory.

    Returns percentages of the migration that are fully automated,
    AI-assisted, or require manual work.
    """
    # Count objects by automation category.
    total_objects = 0
    auto_weight = 0.0
    ai_weight = 0.0
    manual_weight = 0.0

    auto_includes: list[str] = []
    ai_includes: list[str] = []
    manual_includes: list[str] = []

    # Standard tables — 100% automated.
    table_count = len(inventory.tables)
    if table_count:
        total_objects += table_count
        auto_weight += table_count * 100.0
        auto_includes.extend([
            "schema DDL conversion",
            "data type mapping",
            "collation conversion",
            "index recreation",
            "data transfer orchestration",
            "row-level validation",
        ])

    # Foreign keys — 100% automated (kept in DDL).
    if inventory.foreign_keys:
        fk_count = len(inventory.foreign_keys)
        total_objects += fk_count
        auto_weight += fk_count * 100.0

    # FULLTEXT indexes — 95% automated.
    fulltext_count = sum(1 for idx in inventory.indexes if idx.index_type.upper() == "FULLTEXT")
    if fulltext_count:
        total_objects += fulltext_count
        auto_weight += fulltext_count * 95.0
        manual_weight += fulltext_count * 5.0

    # Stored procedures — varies by difficulty.
    procedures = [r for r in inventory.routines if r.routine_type == "PROCEDURE"]
    ai_index = {}
    if ai_analysis:
        ai_index = {
            f"{a.routine_schema}.{a.routine_name}": a for a in ai_analysis
        }
    for proc in procedures:
        key = f"{proc.routine_schema}.{proc.routine_name}"
        if key in ai_index:
            difficulty = ai_index[key].difficulty
        else:
            difficulty = _classify_sp_difficulty(proc.routine_definition)
        auto_pct, ai_pct, man_pct = _SP_AUTOMATION[difficulty]
        total_objects += 1
        auto_weight += auto_pct
        ai_weight += ai_pct
        manual_weight += man_pct
        ai_includes.append(
            f"stored procedure {proc.routine_schema}.{proc.routine_name} "
            f"({difficulty.value}, AI-generated, needs review)"
        )

    # Triggers — 80% AI-assisted.
    if inventory.triggers:
        trg_count = len(inventory.triggers)
        total_objects += trg_count
        ai_weight += trg_count * 80.0
        manual_weight += trg_count * 20.0
        ai_includes.append(
            f"{trg_count} trigger(s) → middleware (AI-generated, needs review)"
        )

    # Events — mostly manual.
    if inventory.events:
        evt_count = len(inventory.events)
        total_objects += evt_count
        auto_weight += evt_count * 60.0
        manual_weight += evt_count * 40.0
        manual_includes.append(f"{evt_count} event(s) → external scheduler")

    # Spatial columns — mostly manual.
    spatial_types = {"geometry", "point", "linestring", "polygon", "multipoint",
                     "multilinestring", "multipolygon", "geometrycollection"}
    spatial_count = sum(1 for c in inventory.columns if c.data_type.lower() in spatial_types)
    if spatial_count:
        total_objects += spatial_count
        auto_weight += spatial_count * 30.0
        manual_weight += spatial_count * 70.0
        manual_includes.append("spatial column conversion (requires design review)")

    # Always-manual items.
    manual_includes.extend([
        "application connection string cutover",
        "business logic validation",
        "performance tuning post-migration",
    ])

    # Compute percentages.
    if total_objects == 0:
        return AutomationCoverage(
            fully_automated_pct=100.0,
            fully_automated_includes=["No objects to migrate"],
        )

    total_weight = auto_weight + ai_weight + manual_weight
    if total_weight == 0:
        total_weight = 1.0

    coverage = AutomationCoverage(
        fully_automated_pct=round(auto_weight / total_weight * 100, 1),
        fully_automated_includes=auto_includes,
        ai_assisted_pct=round(ai_weight / total_weight * 100, 1),
        ai_assisted_includes=ai_includes,
        manual_required_pct=round(manual_weight / total_weight * 100, 1),
        manual_required_includes=manual_includes,
    )

    logger.info(
        "Automation: %.1f%% auto, %.1f%% AI-assisted, %.1f%% manual",
        coverage.fully_automated_pct,
        coverage.ai_assisted_pct,
        coverage.manual_required_pct,
    )
    return coverage
