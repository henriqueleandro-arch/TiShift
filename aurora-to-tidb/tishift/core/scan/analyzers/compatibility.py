"""Compatibility analyzer.

Takes a SchemaInventory and returns an AssessmentResult listing all
blockers, warnings, and informational issues found.
"""

from __future__ import annotations

import logging

from tishift.core.rules.tidb_compat import SPATIAL_TYPES, UNSUPPORTED_COLLATIONS
from tishift.models import (
    AssessmentResult,
    Issue,
    SchemaInventory,
    Severity,
)

logger = logging.getLogger(__name__)


def assess_compatibility(inventory: SchemaInventory) -> AssessmentResult:
    """Assess TiDB compatibility from a schema inventory."""
    result = AssessmentResult()

    # ---- Stored procedures ----
    for routine in inventory.routines:
        if routine.routine_type == "PROCEDURE":
            result.warnings.append(
                Issue(
                    type="stored_procedure",
                    object_name=f"{routine.routine_schema}.{routine.routine_name}",
                    severity=Severity.WARNING,
                    message=(
                        "TiDB parses stored procedures but cannot execute them; "
                        "must be refactored to application code"
                    ),
                    suggestion="Use tishift convert --ai to generate application code replacement",
                )
            )
        elif routine.routine_type == "FUNCTION":
            result.warnings.append(
                Issue(
                    type="user_defined_function",
                    object_name=f"{routine.routine_schema}.{routine.routine_name}",
                    severity=Severity.WARNING,
                    message=(
                        "TiDB does not support user-defined functions; "
                        "must be refactored to application code"
                    ),
                    suggestion="Move function logic into application layer",
                )
            )

    # ---- Triggers ----
    for trigger in inventory.triggers:
        result.warnings.append(
            Issue(
                type="trigger",
                object_name=f"{trigger.trigger_schema}.{trigger.trigger_name}",
                severity=Severity.WARNING,
                message=(
                    f"TiDB does not support triggers; "
                    f"{trigger.action_timing} {trigger.event_manipulation} "
                    f"on {trigger.event_object_table} must move to application layer"
                ),
                suggestion="Generate middleware using tishift convert",
            )
        )

    # ---- Events ----
    for event in inventory.events:
        result.warnings.append(
            Issue(
                type="event",
                object_name=f"{event.event_schema}.{event.event_name}",
                severity=Severity.WARNING,
                message="TiDB does not support scheduled events",
                suggestion="Move to external scheduler (cron, Kubernetes CronJob)",
            )
        )

    # ---- Spatial/GIS columns ----
    spatial_cols = [
        c for c in inventory.columns if c.data_type.lower() in SPATIAL_TYPES
    ]
    if spatial_cols:
        tables_with_spatial = {f"{c.table_schema}.{c.table_name}" for c in spatial_cols}
        result.blockers.append(
            Issue(
                type="spatial_gis",
                object_name=", ".join(sorted(tables_with_spatial)),
                severity=Severity.BLOCKER,
                message=(
                    f"Found {len(spatial_cols)} spatial column(s) in "
                    f"{len(tables_with_spatial)} table(s); TiDB does not support spatial types"
                ),
                suggestion="Convert spatial columns to JSON or numeric lat/lng columns",
            )
        )

    # ---- FULLTEXT indexes ----
    fulltext_indexes = [
        idx for idx in inventory.indexes if idx.index_type.upper() == "FULLTEXT"
    ]
    if fulltext_indexes:
        result.warnings.append(
            Issue(
                type="fulltext_index",
                object_name=", ".join(
                    f"{idx.table_schema}.{idx.table_name}.{idx.index_name}"
                    for idx in fulltext_indexes
                ),
                severity=Severity.WARNING,
                message=(
                    f"Found {len(fulltext_indexes)} FULLTEXT index(es); "
                    "limited support in TiDB (Cloud only)"
                ),
                suggestion="Consider external search (Elasticsearch, MeiliSearch) for self-hosted TiDB",
            )
        )

    # ---- Foreign keys ----
    if inventory.foreign_keys:
        result.info.append(
            Issue(
                type="foreign_key",
                object_name=f"{len(inventory.foreign_keys)} foreign key(s)",
                severity=Severity.INFO,
                message=(
                    f"Found {len(inventory.foreign_keys)} foreign key(s); "
                    "TiDB parses FK constraints, enforcement available since v6.6+"
                ),
                suggestion="Keep in DDL; consider application-layer validation as backup",
            )
        )

    # ---- Unsupported collations ----
    for cs in inventory.charset_usage:
        if cs.collation_name and cs.collation_name.lower() in UNSUPPORTED_COLLATIONS:
            result.warnings.append(
                Issue(
                    type="unsupported_collation",
                    object_name=cs.collation_name,
                    severity=Severity.WARNING,
                    message=(
                        f"Collation '{cs.collation_name}' on {cs.column_count} column(s) "
                        "is not supported in TiDB"
                    ),
                    suggestion="Map to utf8mb4_general_ci or utf8mb4_bin during conversion",
                )
            )

    # ---- Non-utf8mb4 character sets ----
    non_utf8_charsets = [
        cs for cs in inventory.charset_usage
        if cs.character_set_name and cs.character_set_name.lower() != "utf8mb4"
    ]
    for cs in non_utf8_charsets:
        result.info.append(
            Issue(
                type="charset",
                object_name=f"{cs.character_set_name}/{cs.collation_name}",
                severity=Severity.INFO,
                message=(
                    f"Character set '{cs.character_set_name}' on {cs.column_count} column(s); "
                    "TiDB supports it but utf8mb4 is recommended"
                ),
                suggestion="Consider migrating to utf8mb4",
            )
        )

    logger.info(
        "Assessment: %d blockers, %d warnings, %d info",
        len(result.blockers),
        len(result.warnings),
        len(result.info),
    )
    return result
