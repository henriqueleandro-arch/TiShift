# Scoring Engine — Detailed Pseudocode

This reference is loaded by the SKILL.md during Phase 4 (Score).
Follow the pseudocode exactly — every deduction must be traceable.

## Category 1: Schema Compatibility (30 points max)

```
SET schema_score = 30

SET sp_deduction = MIN(stored_procedure_count * 2, 10)
SET schema_score = schema_score - sp_deduction

SET trigger_deduction = MIN(trigger_count * 2, 10)
SET schema_score = schema_score - trigger_deduction

SET fk_deduction = MIN(foreign_key_count * 1, 5)
SET schema_score = schema_score - fk_deduction

IF has_spatial_columns = TRUE THEN SET schema_score = schema_score - 3
IF has_fulltext_indexes = TRUE AND $DEPLOYMENT_TARGET = "self-hosted" THEN SET schema_score = schema_score - 2
# When $DEPLOYMENT_TARGET = "cloud", skip this deduction — TiDB Cloud supports FULLTEXT natively.

SET collation_deduction = unsupported_collation_count * 1
SET schema_score = schema_score - collation_deduction

SET event_deduction = event_count * 1
SET schema_score = schema_score - event_deduction

IF schema_score < 0 THEN SET schema_score = 0
```

## Category 2: Data Complexity (20 points max)

```
SET data_score = 20
SET total_data_gb = total_data_mb / 1024

IF total_data_gb > 5000 THEN
    SET data_score = data_score - 10
ELSE IF total_data_gb > 1000 THEN
    SET data_score = data_score - 5
ELSE IF total_data_gb > 500 THEN
    SET data_score = data_score - 2

SET largest_table_gb = largest_table_mb / 1024
IF largest_table_gb > 100 THEN SET data_score = data_score - 2

SET blob_deduction = MIN(longblob_column_count, 5)
SET data_score = data_score - blob_deduction

IF table_count > 1000 THEN SET data_score = data_score - 2

IF data_score < 0 THEN SET data_score = 0
```

## Category 3: Query Compatibility (20 points max)

Most migrations won't have a query log available. Default to 18/20 in that case.

```
IF no query log is available THEN
    SET query_score = 18
    NOTE: "Assumed 18/20 — no query log provided"
ELSE
    SET query_score = 20
    IF xa_transaction_found THEN SET query_score = query_score - 2
    IF get_lock_found THEN SET query_score = query_score - 2
    IF sql_calc_found_rows_found THEN SET query_score = query_score - 2
    SET unsupported_func_deduction = MIN(unsupported_function_count, 10)
    SET query_score = query_score - unsupported_func_deduction

IF query_score < 0 THEN SET query_score = 0
```

## Category 4: Procedural Code (20 points max)

```
IF stored_procedure_count = 0 AND trigger_count = 0 AND event_count = 0 THEN
    SET proc_score = 20
    NOTE: "No procedural code found"
ELSE
    SET proc_score = 20

    FOR EACH stored procedure:
        Count lines in routine_definition (from Step 2.5)
        Check for CURSOR, PREPARE, EXECUTE, CALL, TEMPORARY keywords
        IF has PREPARE or EXECUTE or CALL:
            IF lines > 100 THEN deduct 5 (requires_redesign)
            ELSE deduct 5 (complex)
        ELSE IF lines < 10 AND no CURSOR AND control_flow <= 1:
            deduct 1 (trivial)
        ELSE IF lines < 30 AND no CURSOR:
            deduct 2 (simple)
        ELSE IF has CURSOR or TEMPORARY or lines >= 100:
            deduct 3 (moderate)
        ELSE:
            deduct 2 (simple)
        SET proc_score = proc_score - deduction

    FOR EACH trigger:
        SET proc_score = proc_score - 2

    FOR EACH event:
        SET proc_score = proc_score - 1

IF proc_score < 0 THEN SET proc_score = 0
```

## Category 5: Operational Readiness (10 points max)

`binlog_format = "ROW"` is the correct value for CDC replication — do not deduct for it.
Only deduct if the value is STATEMENT or MIXED, which means CDC won't work without a config change.

```
SET ops_score = 10

IF binlog_format != "ROW" THEN SET ops_score = ops_score - 5

IF mysql_version starts with "5.7" THEN SET ops_score = ops_score - 2

IF character_set_server != "utf8mb4" THEN SET ops_score = ops_score - 1

IF lower_case_table_names is NOT 0 AND NOT 2 THEN SET ops_score = ops_score - 2

IF ops_score < 0 THEN SET ops_score = 0
```

## Calculate Total

```
SET total = schema_score + data_score + query_score + proc_score + ops_score

IF total >= 90 THEN rating = "excellent"
ELSE IF total >= 75 THEN rating = "good"
ELSE IF total >= 50 THEN rating = "moderate"
ELSE IF total >= 25 THEN rating = "challenging"
ELSE rating = "difficult"
```

## Output Format

```json
{
  "schema_compatibility": {"score": N, "max": 30, "deductions": ["description of each deduction"]},
  "data_complexity": {"score": N, "max": 20, "deductions": ["..."]},
  "query_compatibility": {"score": N, "max": 20, "deductions": ["..."]},
  "procedural_code": {"score": N, "max": 20, "deductions": ["..."]},
  "operational_readiness": {"score": N, "max": 10, "deductions": ["..."]},
  "total": N,
  "rating": "excellent|good|moderate|challenging|difficult"
}
```
