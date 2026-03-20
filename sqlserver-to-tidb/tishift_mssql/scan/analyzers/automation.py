"""Automation coverage estimator."""

from __future__ import annotations

from tishift_mssql.models import AssessmentResult, AutomationCoverage, FeatureScanResult, SchemaInventory


def compute_automation(
    inventory: SchemaInventory,
    features: FeatureScanResult,
    assessment: AssessmentResult,
) -> AutomationCoverage:
    """Estimate fully-auto / AI-assisted / manual migration portions."""
    coverage = AutomationCoverage()

    manual_weight = 0
    ai_weight = 0

    manual_weight += len(assessment.blockers) * 2
    manual_weight += len(inventory.triggers) * 3
    manual_weight += len(inventory.assemblies) * 4
    ai_weight += len(inventory.routines)
    ai_weight += len(features.usages) // 5

    manual_pct = min(85.0, float(manual_weight))
    ai_pct = min(70.0, float(ai_weight))
    auto_pct = max(0.0, 100.0 - manual_pct - ai_pct)

    coverage.manual_required_pct = round(manual_pct, 1)
    coverage.ai_assisted_pct = round(ai_pct, 1)
    coverage.fully_automated_pct = round(auto_pct, 1)

    if inventory.tables:
        coverage.fully_automated_includes.append("Table DDL and baseline index conversion")
    if inventory.routines:
        coverage.ai_assisted_includes.append("Stored procedure/function conversion suggestions")
    if inventory.triggers:
        coverage.manual_required_includes.append("Trigger logic reimplementation")
    if inventory.assemblies:
        coverage.manual_required_includes.append("CLR assembly behavior redesign")

    return coverage
