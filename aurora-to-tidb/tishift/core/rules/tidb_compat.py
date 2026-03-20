"""TiDB compatibility rules.

This module is the single source of truth for what Aurora MySQL features
are supported, partially supported, or unsupported in TiDB.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tishift.models import Severity


class RuleCategory(str, Enum):
    BLOCKER = "blocker"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class CompatibilityRule:
    """A single compatibility rule."""
    id: str
    category: RuleCategory
    feature: str
    description: str
    scanner_action: str
    converter_action: str


# ---------------------------------------------------------------------------
# Hard blockers — TiDB cannot do these
# ---------------------------------------------------------------------------

BLOCKER_RULES: list[CompatibilityRule] = [
    CompatibilityRule(
        id="BLK-001",
        category=RuleCategory.BLOCKER,
        feature="stored_procedures",
        description="TiDB parses stored procedures but cannot execute them",
        scanner_action="Flag each SP with difficulty rating and score impact",
        converter_action="Generate application code replacement",
    ),
    CompatibilityRule(
        id="BLK-002",
        category=RuleCategory.BLOCKER,
        feature="triggers",
        description="TiDB parses triggers but cannot execute them",
        scanner_action="Flag each trigger with score impact",
        converter_action="Generate application middleware",
    ),
    CompatibilityRule(
        id="BLK-003",
        category=RuleCategory.BLOCKER,
        feature="user_defined_functions",
        description="TiDB does not support user-defined functions (UDFs)",
        scanner_action="Flag UDFs with score impact",
        converter_action="Generate application function",
    ),
    CompatibilityRule(
        id="BLK-004",
        category=RuleCategory.BLOCKER,
        feature="spatial_gis",
        description="TiDB does not support spatial/GIS types or spatial indexes",
        scanner_action="Block if spatial columns are critical",
        converter_action="Convert spatial columns to JSON/TEXT",
    ),
    CompatibilityRule(
        id="BLK-005",
        category=RuleCategory.BLOCKER,
        feature="xml_functions",
        description="TiDB does not support XML functions (ExtractValue, UpdateXML)",
        scanner_action="Flag XML function usage with score impact",
        converter_action="Suggest JSON equivalent functions",
    ),
    CompatibilityRule(
        id="BLK-006",
        category=RuleCategory.BLOCKER,
        feature="xa_transactions",
        description="TiDB does not support XA distributed transactions",
        scanner_action="Flag XA usage with score impact",
        converter_action="Suggest redesign with standard transactions or saga pattern",
    ),
    CompatibilityRule(
        id="BLK-007",
        category=RuleCategory.BLOCKER,
        feature="scheduled_events",
        description="TiDB does not support MySQL scheduled events",
        scanner_action="Flag each event",
        converter_action="Generate cron/CronJob equivalent",
    ),
]

# ---------------------------------------------------------------------------
# Warnings — works differently in TiDB
# ---------------------------------------------------------------------------

WARNING_RULES: list[CompatibilityRule] = [
    CompatibilityRule(
        id="WRN-001",
        category=RuleCategory.WARNING,
        feature="foreign_keys",
        description="TiDB parses FKs; enforcement available since v6.6+",
        scanner_action="Warn about partial enforcement",
        converter_action="Keep DDL, add explanatory comment",
    ),
    CompatibilityRule(
        id="WRN-002",
        category=RuleCategory.WARNING,
        feature="fulltext_indexes",
        description="FULLTEXT indexes have limited support (TiDB Cloud only)",
        scanner_action="Warn if fulltext indexes are used",
        converter_action="Keep or remove based on target environment",
    ),
    CompatibilityRule(
        id="WRN-003",
        category=RuleCategory.WARNING,
        feature="get_lock",
        description="GET_LOCK/RELEASE_LOCK have limited implementation in TiDB",
        scanner_action="Warn if used in queries",
        converter_action="Suggest Redis-based distributed locking",
    ),
    CompatibilityRule(
        id="WRN-004",
        category=RuleCategory.WARNING,
        feature="auto_increment",
        description="AUTO_INCREMENT generates unique but not sequential values in TiDB",
        scanner_action="Warn if application depends on sequential ordering",
        converter_action="Add comment, suggest AUTO_RANDOM for non-sequential PKs",
    ),
    CompatibilityRule(
        id="WRN-005",
        category=RuleCategory.WARNING,
        feature="sql_calc_found_rows",
        description="SQL_CALC_FOUND_ROWS works but is not optimized in TiDB",
        scanner_action="Warn if used",
        converter_action="Suggest separate COUNT(*) query",
    ),
    CompatibilityRule(
        id="WRN-006",
        category=RuleCategory.WARNING,
        feature="savepoint",
        description="SAVEPOINT supported in pessimistic mode only",
        scanner_action="Warn if optimistic mode is target",
        converter_action="Add comment about mode requirements",
    ),
    CompatibilityRule(
        id="WRN-007",
        category=RuleCategory.WARNING,
        feature="group_by_behavior",
        description="TiDB enforces ONLY_FULL_GROUP_BY strictly by default",
        scanner_action="Info — check sql_mode differences",
        converter_action="Adjust non-aggregated GROUP BY queries",
    ),
    CompatibilityRule(
        id="WRN-008",
        category=RuleCategory.WARNING,
        feature="temporary_tables_in_sp",
        description="Temporary tables in stored procedures not applicable (SPs unsupported)",
        scanner_action="Warn as part of SP analysis",
        converter_action="Refactor during SP conversion",
    ),
]

# ---------------------------------------------------------------------------
# Unsupported collations (TiDB supports a subset)
# ---------------------------------------------------------------------------

# Collations that TiDB does NOT support.
UNSUPPORTED_COLLATIONS: set[str] = {
    "utf8mb4_0900_ai_ci",
    "utf8mb4_0900_as_ci",
    "utf8mb4_0900_as_cs",
    "utf8mb4_de_pb_0900_ai_ci",
    "utf8mb4_de_pb_0900_as_cs",
    "utf8mb4_es_0900_ai_ci",
    "utf8mb4_es_0900_as_cs",
    "utf8mb4_es_trad_0900_ai_ci",
    "utf8mb4_es_trad_0900_as_cs",
    "utf8mb4_hr_0900_ai_ci",
    "utf8mb4_hr_0900_as_cs",
    "utf8mb4_hu_0900_ai_ci",
    "utf8mb4_hu_0900_as_cs",
    "utf8mb4_is_0900_ai_ci",
    "utf8mb4_is_0900_as_cs",
    "utf8mb4_ja_0900_as_cs",
    "utf8mb4_ja_0900_as_cs_ks",
    "utf8mb4_la_0900_ai_ci",
    "utf8mb4_la_0900_as_cs",
    "utf8mb4_lt_0900_ai_ci",
    "utf8mb4_lt_0900_as_cs",
    "utf8mb4_lv_0900_ai_ci",
    "utf8mb4_lv_0900_as_cs",
    "utf8mb4_pl_0900_ai_ci",
    "utf8mb4_pl_0900_as_cs",
    "utf8mb4_ro_0900_ai_ci",
    "utf8mb4_ro_0900_as_cs",
    "utf8mb4_sk_0900_ai_ci",
    "utf8mb4_sk_0900_as_cs",
    "utf8mb4_sl_0900_ai_ci",
    "utf8mb4_sl_0900_as_cs",
    "utf8mb4_sv_0900_ai_ci",
    "utf8mb4_sv_0900_as_cs",
    "utf8mb4_tr_0900_ai_ci",
    "utf8mb4_tr_0900_as_cs",
    "utf8mb4_vi_0900_ai_ci",
    "utf8mb4_vi_0900_as_cs",
    "utf8mb4_zh_0900_as_cs",
}

# Spatial/GIS column types that TiDB does not support.
# Includes "geomcollection" (MySQL 8.0 alias for "geometrycollection").
SPATIAL_TYPES: set[str] = {
    "geometry",
    "point",
    "linestring",
    "polygon",
    "multipoint",
    "multilinestring",
    "multipolygon",
    "geometrycollection",
    "geomcollection",
}

# Functions that TiDB does NOT support.
UNSUPPORTED_FUNCTIONS: set[str] = {
    "extractvalue",
    "updatexml",
    "xml_extract",
    "st_distance",
    "st_within",
    "st_contains",
    "st_intersects",
    "st_area",
    "st_length",
    "st_buffer",
    "st_centroid",
    "st_union",
    "st_astext",
    "st_geomfromtext",
    "st_srid",
    "mbrcontains",
    "mbrcoveredby",
    "mbrcovers",
    "mbrdisjoint",
    "mbrequals",
    "mbrintersects",
    "mbroverlaps",
    "mbrtouches",
    "mbrwithin",
}
