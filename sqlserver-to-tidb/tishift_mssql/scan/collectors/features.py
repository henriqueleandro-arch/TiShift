"""Feature usage collector using regex scanning."""

from __future__ import annotations

from tishift_mssql.models import FeatureScanResult, FeatureUsage, SchemaInventory
from tishift_mssql.rules.tsql_patterns import TSQL_PATTERNS


def collect_features(inventory: SchemaInventory) -> FeatureScanResult:
    """Scan routine/trigger/view definitions for unsupported T-SQL constructs.

    Records every occurrence (not just the first) so the report can show
    accurate counts per pattern.
    """
    result = FeatureScanResult()

    def scan_block(definition: str | None, object_type: str, object_name: str) -> None:
        if not definition:
            return
        for name, pattern in TSQL_PATTERNS.items():
            for match in pattern.finditer(definition):
                start = max(0, match.start() - 20)
                end = min(len(definition), match.end() + 20)
                result.usages.append(
                    FeatureUsage(
                        pattern_name=name,
                        object_type=object_type,
                        object_name=object_name,
                        matched_text=definition[start:end],
                    )
                )

    for routine in inventory.routines:
        scan_block(routine.definition, "routine", f"{routine.schema_name}.{routine.routine_name}")
    for trigger in inventory.triggers:
        scan_block(trigger.definition, "trigger", f"{trigger.schema_name}.{trigger.trigger_name}")
    for view in inventory.views:
        scan_block(view.definition, "view", f"{view.schema_name}.{view.view_name}")

    return result
