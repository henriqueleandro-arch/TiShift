"""Migration readiness scoring engine.

Implements the 5-category weighted scoring methodology from the spec:
- Schema Compatibility (30 pts)
- Data Complexity (20 pts)
- Query Compatibility (20 pts)
- Procedural Code (20 pts)
- Operational Readiness (10 pts)
"""

from __future__ import annotations

import logging

from tishift.models import (
    AuroraMetadata,
    CategoryScore,
    DataProfile,
    QueryPatterns,
    SchemaInventory,
    ScoringResult,
    SPAIAnalysis,
    SPDifficulty,
    TargetDeployment,
)

logger = logging.getLogger(__name__)


def _classify_sp_difficulty(definition: str | None) -> SPDifficulty:
    """Classify stored procedure difficulty from its definition text."""
    if definition is None:
        return SPDifficulty.SIMPLE

    text = definition.upper()
    lines = [l.strip() for l in definition.splitlines() if l.strip()]
    loc = len(lines)

    has_cursors = "CURSOR" in text
    has_dynamic_sql = "PREPARE" in text or "EXECUTE" in text
    has_temp_tables = "TEMPORARY" in text
    has_nested_calls = "CALL " in text
    control_flow = sum(
        1 for kw in ("IF ", "WHILE ", "LOOP ", "CASE ") if kw in text
    )

    # Dynamic SQL and nested calls are always complex — check first.
    if has_dynamic_sql or has_nested_calls:
        if loc > 100:
            return SPDifficulty.REQUIRES_REDESIGN
        return SPDifficulty.COMPLEX

    if loc < 10 and not has_cursors and control_flow <= 1:
        return SPDifficulty.TRIVIAL
    if loc < 30 and not has_cursors:
        return SPDifficulty.SIMPLE
    if has_cursors or has_temp_tables or loc >= 100:
        return SPDifficulty.MODERATE
    return SPDifficulty.SIMPLE


def score_schema_compatibility(
    inventory: SchemaInventory,
    target: TargetDeployment = TargetDeployment.CLOUD,
) -> CategoryScore:
    """Schema Compatibility — 30 points max."""
    score = 30
    deductions: list[str] = []

    # Stored procedures: -2 each, up to -10
    sp_count = sum(1 for r in inventory.routines if r.routine_type == "PROCEDURE")
    sp_deduction = min(sp_count * 2, 10)
    if sp_deduction:
        score -= sp_deduction
        deductions.append(f"-{sp_deduction} for {sp_count} stored procedure(s)")

    # Triggers: -2 each, up to -10
    trg_deduction = min(len(inventory.triggers) * 2, 10)
    if trg_deduction:
        score -= trg_deduction
        deductions.append(f"-{trg_deduction} for {len(inventory.triggers)} trigger(s)")

    # Foreign keys: -1 each, up to -5
    fk_deduction = min(len(inventory.foreign_keys), 5)
    if fk_deduction:
        score -= fk_deduction
        deductions.append(f"-{fk_deduction} for {len(inventory.foreign_keys)} foreign key(s)")

    # Spatial/GIS columns: -3 if any exist
    from tishift.core.rules.tidb_compat import SPATIAL_TYPES
    has_spatial = any(c.data_type.lower() in SPATIAL_TYPES for c in inventory.columns)
    if has_spatial:
        score -= 3
        deductions.append("-3 for spatial/GIS columns")

    # FULLTEXT indexes: -2 if any (self-hosted only; TiDB Cloud supports FULLTEXT)
    if target == TargetDeployment.SELF_HOSTED:
        has_fulltext = any(idx.index_type.upper() == "FULLTEXT" for idx in inventory.indexes)
        if has_fulltext:
            score -= 2
            deductions.append("-2 for FULLTEXT indexes (self-hosted only)")

    # Unsupported collations: -1 each
    from tishift.core.rules.tidb_compat import UNSUPPORTED_COLLATIONS
    unsupported_count = sum(
        1 for cs in inventory.charset_usage
        if cs.collation_name and cs.collation_name.lower() in UNSUPPORTED_COLLATIONS
    )
    if unsupported_count:
        score -= unsupported_count
        deductions.append(f"-{unsupported_count} for unsupported collation(s)")

    # Events: -1 each
    evt_deduction = len(inventory.events)
    if evt_deduction:
        score -= evt_deduction
        deductions.append(f"-{evt_deduction} for scheduled event(s)")

    return CategoryScore(
        name="schema_compatibility", score=max(score, 0), max_score=30, deductions=deductions
    )


def score_data_complexity(profile: DataProfile) -> CategoryScore:
    """Data Complexity — 20 points max."""
    score = 20
    deductions: list[str] = []
    total_gb = profile.total_data_mb / 1024

    if total_gb > 5000:
        score -= 10
        deductions.append("-10 for total data > 5 TB")
    elif total_gb > 1000:
        score -= 5
        deductions.append("-5 for total data > 1 TB")
    elif total_gb > 500:
        score -= 2
        deductions.append("-2 for total data > 500 GB")

    # Single table > 100 GB
    for ts in profile.table_sizes:
        if ts.total_mb / 1024 > 100:
            score -= 2
            deductions.append(f"-2 for table {ts.table_schema}.{ts.table_name} > 100 GB")
            break  # only deduct once

    # LONGBLOB columns: -1 each, up to -5
    longblob_count = sum(
        1 for b in profile.blob_columns if b.data_type.lower() == "longblob"
    )
    blob_deduction = min(longblob_count, 5)
    if blob_deduction:
        score -= blob_deduction
        deductions.append(f"-{blob_deduction} for {longblob_count} LONGBLOB column(s)")

    # > 1000 tables
    if len(profile.table_sizes) > 1000:
        score -= 2
        deductions.append(f"-2 for {len(profile.table_sizes)} tables (> 1000)")

    return CategoryScore(
        name="data_complexity", score=max(score, 0), max_score=20, deductions=deductions
    )


def score_query_compatibility(
    query_patterns: QueryPatterns | None,
) -> CategoryScore:
    """Query Compatibility — 20 points max."""
    if query_patterns is None:
        # Not scored — assume 18/20 per spec.
        return CategoryScore(
            name="query_compatibility",
            score=18,
            max_score=20,
            deductions=["Assumed 18/20 (--include-query-log not used)"],
        )

    score = 20
    deductions: list[str] = []

    # Count unique constructs
    constructs: dict[str, int] = {}
    for issue in query_patterns.issues:
        constructs[issue.construct] = constructs.get(issue.construct, 0) + 1

    if "XA_TRANSACTION" in constructs:
        score -= 2
        deductions.append("-2 for XA transaction patterns")

    get_lock_count = constructs.get("GET_LOCK", 0) + constructs.get("RELEASE_LOCK", 0)
    if get_lock_count:
        score -= min(get_lock_count, 2)
        deductions.append(f"-{min(get_lock_count, 2)} for GET_LOCK/RELEASE_LOCK usage")

    if "SQL_CALC_FOUND_ROWS" in constructs:
        score -= 2
        deductions.append("-2 for SQL_CALC_FOUND_ROWS usage")

    # General unsupported function usage: -1 each, up to -10
    unsupported_count = sum(
        v for k, v in constructs.items()
        if k not in ("XA_TRANSACTION", "GET_LOCK", "RELEASE_LOCK", "SQL_CALC_FOUND_ROWS")
    )
    func_deduction = min(unsupported_count, 10)
    if func_deduction:
        score -= func_deduction
        deductions.append(f"-{func_deduction} for {unsupported_count} unsupported function usage(s)")

    return CategoryScore(
        name="query_compatibility", score=max(score, 0), max_score=20, deductions=deductions
    )


def score_procedural_code(
    inventory: SchemaInventory,
    ai_analysis: list[SPAIAnalysis] | None = None,
) -> CategoryScore:
    """Procedural Code — 20 points max."""
    score = 20
    deductions: list[str] = []

    procedures = [r for r in inventory.routines if r.routine_type == "PROCEDURE"]
    if not procedures and not inventory.triggers and not inventory.events:
        return CategoryScore(
            name="procedural_code", score=20, max_score=20, deductions=["No procedural code found"]
        )

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
        if difficulty == SPDifficulty.TRIVIAL:
            score -= 1
            deductions.append(f"-1 for trivial SP: {proc.routine_schema}.{proc.routine_name}")
        elif difficulty == SPDifficulty.SIMPLE:
            score -= 2
            deductions.append(f"-2 for simple SP: {proc.routine_schema}.{proc.routine_name}")
        elif difficulty == SPDifficulty.MODERATE:
            score -= 3
            deductions.append(f"-3 for moderate SP: {proc.routine_schema}.{proc.routine_name}")
        elif difficulty == SPDifficulty.COMPLEX:
            score -= 5
            deductions.append(f"-5 for complex SP: {proc.routine_schema}.{proc.routine_name}")
        elif difficulty == SPDifficulty.REQUIRES_REDESIGN:
            score -= 5
            deductions.append(f"-5 for SP requiring redesign: {proc.routine_schema}.{proc.routine_name}")

    # Triggers count toward procedural code score too (part of code to refactor).
    for trigger in inventory.triggers:
        score -= 2
        deductions.append(f"-2 for trigger: {trigger.trigger_schema}.{trigger.trigger_name}")

    for event in inventory.events:
        score -= 1
        deductions.append(f"-1 for event: {event.event_schema}.{event.event_name}")

    return CategoryScore(
        name="procedural_code", score=max(score, 0), max_score=20, deductions=deductions
    )


def score_operational_readiness(metadata: AuroraMetadata) -> CategoryScore:
    """Operational Readiness — 10 points max."""
    score = 10
    deductions: list[str] = []

    # Binlog format must be ROW for CDC.
    if metadata.binlog_format and metadata.binlog_format.upper() != "ROW":
        score -= 5
        deductions.append(f"-5 for binlog_format={metadata.binlog_format} (must be ROW for CDC)")

    # Aurora 2.x (MySQL 5.7) — approaching EOL.
    if metadata.aurora_version and metadata.aurora_version.startswith("2."):
        score -= 2
        deductions.append("-2 for Aurora 2.x (MySQL 5.7, approaching EOL)")

    # Character set.
    if (
        metadata.character_set_server
        and metadata.character_set_server.lower() != "utf8mb4"
    ):
        score -= 1
        deductions.append(
            f"-1 for character_set_server={metadata.character_set_server} (not utf8mb4)"
        )

    # lower_case_table_names mismatch (TiDB default is 2 on some platforms).
    # We flag if it's set to something other than the common value.
    if metadata.lower_case_table_names is not None and metadata.lower_case_table_names not in (0, 2):
        score -= 2
        deductions.append(
            f"-2 for lower_case_table_names={metadata.lower_case_table_names} "
            "(may differ from TiDB default)"
        )

    return CategoryScore(
        name="operational_readiness", score=max(score, 0), max_score=10, deductions=deductions
    )


def compute_scores(
    inventory: SchemaInventory,
    profile: DataProfile,
    metadata: AuroraMetadata,
    query_patterns: QueryPatterns | None = None,
    ai_analysis: list[SPAIAnalysis] | None = None,
    target: TargetDeployment = TargetDeployment.CLOUD,
) -> ScoringResult:
    """Compute all 5 scoring categories and return the result."""
    result = ScoringResult(
        schema_compatibility=score_schema_compatibility(inventory, target=target),
        data_complexity=score_data_complexity(profile),
        query_compatibility=score_query_compatibility(query_patterns),
        procedural_code=score_procedural_code(inventory, ai_analysis=ai_analysis),
        operational_readiness=score_operational_readiness(metadata),
    )
    logger.info(
        "Scoring complete: %d/100 (%s)",
        result.overall_score,
        result.rating.value,
    )
    return result
