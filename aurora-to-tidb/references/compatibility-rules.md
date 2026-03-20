# TiDB Compatibility Rules

This reference is loaded by the SKILL.md during Phase 3 (Assess Compatibility).
Apply every rule in order against the checklist from Phase 2.5.

## BLOCKERS — TiDB cannot do these

These features are parsed by TiDB's SQL parser but have no runtime implementation.
They will silently fail or error at execution time, not at DDL time — which makes them
especially dangerous because the schema will appear to load correctly.

| ID | Condition | Feature | Action |
|----|-----------|---------|--------|
| BLOCKER-1 | `stored_procedure_count > 0` | Stored procedures — parsed but cannot execute | Convert to application code (Python/Go/Java/JS) |
| BLOCKER-2 | `trigger_count > 0` | Triggers — parsed but cannot execute | Move logic to application middleware |
| BLOCKER-3 | `event_count > 0` | Scheduled events — not supported | Use cron, Kubernetes CronJob, or AWS EventBridge |
| BLOCKER-4 | `has_spatial_columns = TRUE` | Spatial/GIS columns — no spatial index support | Convert columns to JSON with `COMMENT 'was: <original_type>'` |
| BLOCKER-5 | XA transactions detected in query log | XA distributed transactions — not supported | Refactor to single-shard transactions or saga pattern |
| BLOCKER-6 | UDFs detected | User-defined functions — not supported | Convert to application-layer functions |
| BLOCKER-7 | XML functions detected | XML functions (ExtractValue, UpdateXML) — not supported | Process XML in application layer |

## WARNINGS — works differently in TiDB

These features work but behave differently from MySQL. They won't break the migration,
but they can cause subtle bugs if the application makes assumptions about MySQL-specific behavior.

| ID | Condition | Feature | Action |
|----|-----------|---------|--------|
| WARNING-1 | `foreign_key_count > 0` | Foreign keys — enforcement only in TiDB v6.6+ | Keep DDL, validate constraints in application layer for older versions |
| WARNING-2 | `has_fulltext_indexes = TRUE` AND `$DEPLOYMENT_TARGET = self-hosted` | FULLTEXT indexes — supported on TiDB Cloud, not self-hosted | IF self-hosted: use Elasticsearch/Meilisearch. IF cloud: no action needed |
| WARNING-3 | `auto_increment_table_count > 0` | AUTO_INCREMENT — unique but NOT sequential | Each TiDB node allocates ID ranges independently; add comment, consider AUTO_RANDOM for high-insert tables |
| WARNING-4 | `unsupported_collation_count > 0` | Unsupported collations (utf8mb4_0900_* family) | Map to utf8mb4_general_ci; verify sort-order-sensitive queries |
| WARNING-5 | GET_LOCK usage detected | GET_LOCK/RELEASE_LOCK — limited implementation | Test advisory locking behavior; consider Redis-based locks |
| WARNING-6 | SQL_CALC_FOUND_ROWS detected | SQL_CALC_FOUND_ROWS — works but triggers full table scan | Replace with separate COUNT(*) query |
| WARNING-7 | SAVEPOINT usage detected | SAVEPOINT — pessimistic mode only | Ensure pessimistic transaction mode is enabled (default in TiDB) |

## COMPATIBLE — no changes needed

These features are fully supported in TiDB with identical behavior to MySQL:

- InnoDB engine (TiDB's only engine — always compatible)
- JSON columns (full JSON path support)
- ENUM/SET types
- utf8mb4 charset
- Window functions and CTEs
- Prepared statements
- Pessimistic transactions (default mode)
- RANGE/LIST/HASH/KEY partitioning
- Online DDL (distributed implementation)
- LOAD DATA LOCAL INFILE
- Views (standard SQL views)

## Output Format

```json
{
  "blockers": [{"id": "BLOCKER-1", "feature": "...", "count": N, "action": "..."}],
  "warnings": [{"id": "WARNING-3", "feature": "...", "count": N, "action": "..."}],
  "compatible": ["InnoDB", "JSON columns", "..."]
}
```
