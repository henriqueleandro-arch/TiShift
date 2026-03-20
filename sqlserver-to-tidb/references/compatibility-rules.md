# TiDB Compatibility Rules for SQL Server Migrations

## Table of Contents
1. [Blockers](#blockers)
2. [Warnings](#warnings)
3. [T-SQL Feature Detection Patterns](#t-sql-feature-detection-patterns)
4. [Compatible Features](#compatible-features)

---

## Blockers

These are hard stops. TiDB cannot handle these features — they must be redesigned before migration.

| ID | Feature | Why It Blocks | Action |
|---|---|---|---|
| BLOCKER-1 | Stored procedures | TiDB parses CREATE PROCEDURE syntax but has no procedural runtime — they cannot execute | Convert to application code (Python/Go/Java/JS service layer) |
| BLOCKER-2 | Triggers | TiDB parses CREATE TRIGGER but does not fire them | Move logic to application middleware or event hooks |
| BLOCKER-3 | CLR assemblies/modules | No .NET CLR runtime in TiDB | Rewrite CLR code in application language |
| BLOCKER-4 | Linked servers | No distributed query engine (OPENQUERY, four-part names) | Replace with application-level service calls or ETL pipelines |
| BLOCKER-5 | Spatial types (geography/geometry) | No spatial indexes, no ST_* functions | Convert columns to LONGTEXT or JSON, move spatial logic to PostGIS or application |
| BLOCKER-6 | HIERARCHYID | No equivalent type or functions | Convert to VARCHAR(255), implement hierarchy traversal in application (adjacency list or materialized path) |
| BLOCKER-7 | XML data type | No XML type, no XPath/XQuery methods (.value, .query, .nodes) | Convert to LONGTEXT or JSON, port XML queries to application |
| BLOCKER-8 | SQL_VARIANT | No polymorphic type | Convert to JSON with explicit type tracking (loses native type metadata) |
| BLOCKER-9 | FILESTREAM | No filesystem-integrated blob storage | Move files to object storage (S3/GCS), store path in VARCHAR column |
| BLOCKER-10 | MERGE statement | Not supported in TiDB's SQL dialect | Rewrite as separate INSERT + UPDATE + DELETE with explicit conditions |
| BLOCKER-11 | FOR XML / OPENXML | No XML construction or shredding | Replace with JSON_OBJECT/JSON_ARRAY or application-level XML generation |
| BLOCKER-12 | OPENQUERY / OPENROWSET | No ad-hoc distributed queries | Replace with application-level data access or ETL |
| BLOCKER-13 | Server-side cursors | TiDB has no DECLARE CURSOR support | Rewrite as set-based operations (usually more performant anyway) |
| BLOCKER-14 | Service Broker | No message queuing built into TiDB | Replace with Kafka, RabbitMQ, or cloud-native message queue |
| BLOCKER-15 | Extended stored procedures (xp_cmdshell, sp_OA*) | No OS-level execution from database | Move to application or infrastructure automation |

## Warnings

These features work differently in TiDB. They won't block migration but require review and possible adjustment.

| ID | Feature | How It Differs | Action |
|---|---|---|---|
| WARNING-1 | IDENTITY columns | TiDB AUTO_INCREMENT generates unique but non-sequential values (each node allocates ID ranges from PD independently) | Keep AUTO_INCREMENT. Document non-sequential behavior. Consider AUTO_RANDOM for high-insert tables |
| WARNING-2 | Computed columns | TiDB supports GENERATED columns (STORED/VIRTUAL) but only with a subset of functions | Review each computed column. Convert if the expression uses only supported functions, otherwise compute in application |
| WARNING-3 | Filtered indexes | TiDB has no WHERE clause on CREATE INDEX | Use regular indexes with application-level filtering, or redesign queries |
| WARNING-4 | Columnstore indexes | TiDB uses TiFlash (columnar replica) for analytics, not columnstore indexes | Configure TiFlash replicas for analytics-heavy tables |
| WARNING-5 | Memory-optimized tables | No in-memory engine in TiDB | Use standard InnoDB tables. TiDB's block cache handles hot data caching automatically |
| WARNING-6 | Temporal tables | No system-versioned temporal tables | Implement history tracking via application triggers, CDC, or audit tables |
| WARNING-7 | SQL Agent jobs | No built-in job scheduler | Use cron, Kubernetes CronJob, Apache Airflow, or cloud-native scheduler |
| WARNING-8 | SSIS packages | No ETL engine built into TiDB | Redesign with Apache Airflow, dbt, or application-level ETL |
| WARNING-9 | INSTEAD OF triggers | Same as regular triggers — not executed | Implement pre-insert/update validation in application layer |
| WARNING-10 | Collation differences | SQL Server collations (e.g., SQL_Latin1_General_CP1_CI_AS) map to utf8mb4 equivalents but sort/compare semantics may differ subtly | Map CI→utf8mb4_general_ci, CS→utf8mb4_bin. Validate string comparison behavior post-migration |
| WARNING-11 | Deprecated types (IMAGE/TEXT/NTEXT) | These map to LONGBLOB/LONGTEXT but should be modernized | IMAGE→LONGBLOB, TEXT/NTEXT→LONGTEXT |
| WARNING-12 | Heap tables (no clustered index) | TiDB assigns an implicit _tidb_rowid but performance is better with explicit PKs | Add explicit primary key for optimal performance |
| WARNING-13 | Sequences | TiDB supports SEQUENCE but behavior may differ from SQL Server | Validate sequence caching and increment behavior |
| WARNING-14 | Table-valued parameters | No TVP equivalent in TiDB | Redesign API to use JSON arrays or temp tables |

## T-SQL Feature Detection Patterns

Scan routine, trigger, and view definitions (from sys.sql_modules) for these regex patterns to detect unsupported features:

| Pattern | Regex | Maps To |
|---|---|---|
| MERGE | `\bMERGE\b` | BLOCKER-10 |
| FOR XML | `\bFOR\s+XML\b` | BLOCKER-11 |
| OPENXML | `\bOPENXML\b` | BLOCKER-11 |
| OPENQUERY | `\bOPENQUERY\b` | BLOCKER-12 |
| OPENROWSET | `\bOPENROWSET\b` | BLOCKER-12 |
| Cursor | `\bDECLARE\s+\w+\s+CURSOR\b` | BLOCKER-13 |
| Service Broker | `\bCREATE\s+(QUEUE|SERVICE|CONTRACT)\b` | BLOCKER-14 |
| xp_cmdshell | `\bxp_cmdshell\b` | BLOCKER-15 |
| CROSS APPLY | `\bCROSS\s+APPLY\b` | WARNING (query rewrite) |
| OUTER APPLY | `\bOUTER\s+APPLY\b` | WARNING (query rewrite) |
| PIVOT | `\bPIVOT\b` | WARNING (query rewrite) |
| UNPIVOT | `\bUNPIVOT\b` | WARNING (query rewrite) |
| Dynamic SQL | `\bsp_executesql\b` | WARNING (review) |
| Temp tables | `\b#\w+\b` | WARNING (review) |
| TRY/CATCH | `\bBEGIN\s+TRY\b` | WARNING (error handling redesign) |
| OUTPUT clause | `\bOUTPUT\s+(INSERTED|DELETED)\b` | WARNING (no equivalent) |

## Compatible Features

These work identically or have direct equivalents in TiDB — no changes needed:

- INT/BIGINT/SMALLINT/TINYINT numeric types
- DECIMAL/NUMERIC with precision and scale
- VARCHAR/CHAR (mapped to utf8mb4)
- DATE/TIME/DATETIME/DATETIME2 (with precision capping)
- BINARY/VARBINARY
- BIT (as TINYINT(1))
- FLOAT/REAL
- MONEY/SMALLMONEY (as DECIMAL)
- Views (standard SELECT-based)
- Window functions (ROW_NUMBER, RANK, DENSE_RANK, NTILE, LAG, LEAD, etc.)
- Common Table Expressions (WITH ... AS)
- Prepared statements
- Pessimistic transactions (TiDB default)
- RANGE/LIST/HASH partitioning
- JSON columns and JSON functions
- Standard JOINs (INNER, LEFT, RIGHT)
- Subqueries and derived tables
- CASE expressions
- UNION / UNION ALL
- GROUP BY with HAVING
- ORDER BY with OFFSET/FETCH (TiDB uses LIMIT/OFFSET)

## TiDB Cloud Tier-Specific Rules

These apply on top of the base TiDB rules above, depending on the target tier.

### Starter Tier Blockers

| ID | Constraint | Limit | Action |
|---|---|---|---|
| STARTER-BLOCKER-1 | Storage exceeds free tier | 25 GiB | Upgrade to Essential or Dedicated |
| STARTER-BLOCKER-2 | No Changefeeds | N/A | CDC sync impossible — use cutover migration |
| STARTER-BLOCKER-3 | No Data Migration (DM) | N/A | Use ticloud CLI import or direct LOAD DATA |
| STARTER-BLOCKER-4 | No TiDB Lightning | N/A | Use ticloud CLI import for large datasets |

### Starter Tier Warnings

| ID | Constraint | Limit | Action |
|---|---|---|---|
| STARTER-WARNING-1 | Connection limit | 400 (5,000 with spend limit) | Review application connection pooling |
| STARTER-WARNING-2 | Import file size | 250 MiB per console upload | Split CSVs or use `ticloud serverless import start` CLI |
| STARTER-WARNING-3 | RU budget | 250M free/month | Monitor Request Unit consumption post-migration |
| STARTER-WARNING-4 | Transaction timeout | 30 minutes | Batch large operations; avoid long-running transactions |

### Essential Tier Constraints

| ID | Constraint | Action |
|---|---|---|
| ESSENTIAL-BLOCKER-1 | No DM | Use DMS or direct load |
| ESSENTIAL-BLOCKER-2 | No Lightning | Use DMS for large loads or upgrade to Dedicated |
| ESSENTIAL-WARNING-1 | Data > 500 GB | Dedicated may offer better import performance |
