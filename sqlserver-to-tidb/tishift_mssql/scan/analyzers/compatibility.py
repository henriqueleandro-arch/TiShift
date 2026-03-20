"""Compatibility analyzer for SQL Server to TiDB."""

from __future__ import annotations

from tishift_mssql.models import AssessmentResult, DataProfile, FeatureScanResult, Issue, SQLServerMetadata, SchemaInventory, Severity, TierFitResult
from tishift_mssql.rules.tidb_compat import (
    BLOCKER_RULES, WARNING_RULES,
    STARTER_BLOCKERS, STARTER_WARNINGS,
    ESSENTIAL_BLOCKERS, ESSENTIAL_WARNINGS,
)


_FEATURE_TO_RULE = {
    "merge": "merge",
    "for_xml": "for_xml",
    "openxml": "for_xml",
    "openquery": "openquery",
    "openrowset": "openquery",
    "cursor": "cursor",
    "service_broker": "service_broker",
    "table_valued_param": "table_valued_param",
    "sequence": "sequence",
}


def _issue(rule: str, obj: str, severity: Severity, message: str) -> Issue:
    return Issue(type=rule, object_name=obj, severity=severity, message=message)


def assess_compatibility(
    inventory: SchemaInventory,
    features: FeatureScanResult,
    metadata: SQLServerMetadata,
    profile: DataProfile | None = None,
    tier: str = "starter",
) -> AssessmentResult:
    """Assess blockers and warnings from schema inventory and feature scan."""
    result = AssessmentResult()

    for routine in inventory.routines:
        if routine.routine_type.startswith("SQL_STORED") or routine.routine_type.endswith("PROCEDURE"):
            result.blockers.append(
                _issue("stored_procedure", f"{routine.schema_name}.{routine.routine_name}", Severity.BLOCKER, BLOCKER_RULES["stored_procedure"])
            )
        if routine.is_clr:
            result.blockers.append(
                _issue("clr", f"{routine.schema_name}.{routine.routine_name}", Severity.BLOCKER, BLOCKER_RULES["clr"])
            )

    for trigger in inventory.triggers:
        result.blockers.append(
            _issue("trigger", f"{trigger.schema_name}.{trigger.trigger_name}", Severity.BLOCKER, BLOCKER_RULES["trigger"])
        )
        if trigger.is_instead_of:
            result.warnings.append(
                _issue(
                    "instead_of_trigger",
                    f"{trigger.schema_name}.{trigger.trigger_name}",
                    Severity.WARNING,
                    WARNING_RULES["instead_of_trigger"],
                )
            )

    if inventory.assemblies:
        result.blockers.append(_issue("clr", "assemblies", Severity.BLOCKER, BLOCKER_RULES["clr"]))

    if inventory.linked_servers:
        result.blockers.append(_issue("linked_server", "sys.servers", Severity.BLOCKER, BLOCKER_RULES["linked_server"]))

    if inventory.agent_jobs:
        result.warnings.append(_issue("agent_job", "msdb jobs", Severity.WARNING, WARNING_RULES["agent_job"]))

    for table in inventory.tables:
        if table.is_memory_optimized:
            result.warnings.append(
                _issue("memory_optimized", f"{table.schema_name}.{table.table_name}", Severity.WARNING, WARNING_RULES["memory_optimized"])
            )
        if table.is_temporal:
            result.warnings.append(
                _issue("temporal", f"{table.schema_name}.{table.table_name}", Severity.WARNING, WARNING_RULES["temporal"])
            )

    for column in inventory.columns:
        dt = column.data_type.lower()
        obj = f"{column.schema_name}.{column.table_name}.{column.column_name}"
        if column.is_identity:
            result.warnings.append(_issue("identity", obj, Severity.WARNING, WARNING_RULES["identity"]))
        if column.is_computed:
            result.warnings.append(_issue("computed_column", obj, Severity.WARNING, WARNING_RULES["computed_column"]))
        if dt in {"hierarchyid", "geography", "geometry"}:
            result.blockers.append(_issue("spatial", obj, Severity.BLOCKER, BLOCKER_RULES["spatial"]))
        if dt == "xml":
            result.blockers.append(_issue("xml_type", obj, Severity.BLOCKER, BLOCKER_RULES["xml_type"]))
        if dt == "sql_variant":
            result.blockers.append(_issue("sql_variant", obj, Severity.BLOCKER, BLOCKER_RULES["sql_variant"]))

    for idx in inventory.indexes:
        if idx.filter_definition:
            result.warnings.append(
                _issue(
                    "filtered_index",
                    f"{idx.schema_name}.{idx.table_name}.{idx.index_name}",
                    Severity.WARNING,
                    WARNING_RULES["filtered_index"],
                )
            )
        if "COLUMNSTORE" in idx.index_type.upper():
            result.warnings.append(
                _issue(
                    "columnstore",
                    f"{idx.schema_name}.{idx.table_name}.{idx.index_name}",
                    Severity.WARNING,
                    WARNING_RULES["columnstore"],
                )
            )

    for usage in features.usages:
        mapped = _FEATURE_TO_RULE.get(usage.pattern_name)
        if not mapped:
            continue
        if mapped in BLOCKER_RULES:
            result.blockers.append(_issue(mapped, usage.object_name, Severity.BLOCKER, BLOCKER_RULES[mapped]))
        elif mapped in WARNING_RULES:
            result.warnings.append(_issue(mapped, usage.object_name, Severity.WARNING, WARNING_RULES[mapped]))

    if metadata.db_collation and metadata.db_collation not in {"SQL_Latin1_General_CP1_CI_AS"}:
        result.warnings.append(_issue("collation", metadata.db_collation, Severity.WARNING, WARNING_RULES["collation"]))

    # --- Tier-specific constraints ---
    total_mb = profile.total_data_mb if profile else 0.0

    if tier == "starter":
        if total_mb > 25 * 1024:
            result.blockers.append(_issue(
                "starter_storage_limit", f"{total_mb / 1024:.1f} GiB",
                Severity.BLOCKER, STARTER_BLOCKERS["starter_storage_limit"],
            ))
        result.warnings.append(_issue("starter_connection_limit", "Starter tier", Severity.WARNING, STARTER_WARNINGS["starter_connection_limit"]))
        result.warnings.append(_issue("starter_import_size", "Starter tier", Severity.WARNING, STARTER_WARNINGS["starter_import_size"]))
        result.warnings.append(_issue("starter_ru_budget", "Starter tier", Severity.WARNING, STARTER_WARNINGS["starter_ru_budget"]))
        result.warnings.append(_issue("starter_txn_timeout", "Starter tier", Severity.WARNING, STARTER_WARNINGS["starter_txn_timeout"]))
        if metadata.cdc_enabled:
            result.warnings.append(_issue(
                "starter_no_changefeed", "CDC enabled on source",
                Severity.WARNING, STARTER_BLOCKERS["starter_no_changefeed"] + " Migration will require a cutover with downtime.",
            ))

    elif tier == "essential":
        if total_mb > 500 * 1024:
            result.warnings.append(_issue(
                "essential_large_data", f"{total_mb / 1024:.1f} GiB",
                Severity.WARNING, ESSENTIAL_WARNINGS["essential_large_data"],
            ))

    return result


def evaluate_tier_fit(
    profile: DataProfile,
    metadata: SQLServerMetadata,
    inventory: SchemaInventory,
) -> list[TierFitResult]:
    """Evaluate workload fit for each TiDB Cloud tier."""
    total_gib = profile.total_data_mb / 1024
    results = []

    # Starter
    starter_blockers: list[str] = []
    starter_warnings: list[str] = []
    if total_gib > 25:
        starter_blockers.append(f"Data size ({total_gib:.1f} GiB) exceeds Starter 25 GiB free limit")
    elif total_gib > 20:
        starter_warnings.append(f"Data size ({total_gib:.1f} GiB) approaching Starter 25 GiB limit")
    if metadata.cdc_enabled:
        starter_warnings.append("CDC sync not available — requires cutover migration with downtime")
    if any(t.row_count > 10_000_000 for t in inventory.tables):
        starter_warnings.append("Tables with >10M rows may be slow to import via ticloud CLI")
    results.append(TierFitResult(tier="starter", fits=len(starter_blockers) == 0, blockers=starter_blockers, warnings=starter_warnings))

    # Essential
    essential_blockers: list[str] = []
    essential_warnings: list[str] = []
    if total_gib > 500:
        essential_warnings.append(f"Data size ({total_gib:.1f} GiB) is large — Dedicated may offer better import performance")
    results.append(TierFitResult(tier="essential", fits=True, blockers=essential_blockers, warnings=essential_warnings))

    # Dedicated
    results.append(TierFitResult(tier="dedicated", fits=True, blockers=[], warnings=[]))

    return results
