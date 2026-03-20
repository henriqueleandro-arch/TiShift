# TiShift — Aurora MySQL → TiDB Migration Toolkit

## What Is This Document

This is the complete build specification for **TiShift**, PingCAP's open-source migration toolkit for moving databases from AWS Aurora MySQL to TiDB. It's designed so a developer (or Claude Code daemon) can read this top-to-bottom and build the entire thing.

TiShift has **two interfaces on top of one core library**:

| Interface | Who It's For | How It Works |
|---|---|---|
| **CLI** (`tishift` command) | DBAs, CI/CD pipelines, production migrations | Deterministic, scriptable, runs on bastion hosts |
| **MCP Server** (`tishift-mcp`) | AI-first teams, partner demos, exploratory migrations | Conversational, Claude orchestrates tools via runbook |

Both interfaces call the same core Python library. The CLI is the production workhorse. The MCP server is the AI-first experience and sales weapon.

**Core capabilities (available via both CLI and MCP):**

| Capability | What It Does |
|---|---|
| **scan** | Connects read-only to Aurora MySQL, analyzes everything, produces a scored readiness report |
| **convert** | Transforms schemas, rewrites stored procedures, generates TiDB-compatible DDL |
| **load** | Moves data from Aurora to TiDB (full load via DMS or TiDB Lightning) |
| **sync** | Keeps Aurora and TiDB in sync via CDC (binlog replication) during transition |
| **check** | Validates data integrity between Aurora source and TiDB target after migration |

All capabilities share a common config, logging system, and connection management layer.

---

## Architecture Overview

```
                    ┌─────────────────────────────────────────────┐
                    │              User Interfaces                 │
                    │                                             │
                    │   ┌──────────────┐   ┌──────────────────┐  │
                    │   │  CLI (Click)  │   │  MCP Server      │  │
                    │   │              │   │  (FastMCP)        │  │
                    │   │ tishift scan │   │                   │  │
                    │   │ tishift conv │   │ scan_schema       │  │
                    │   │ tishift load │   │ assess_compat     │  │
                    │   │ tishift sync │   │ convert_schema    │  │
                    │   │ tishift check│   │ load_table        │  │
                    │   │              │   │ validate_rows     │  │
                    │   │ Deterministic│   │ ... (12 tools)    │  │
                    │   │ Scriptable   │   │                   │  │
                    │   │ CI/CD ready  │   │ Conversational    │  │
                    │   └──────┬───────┘   │ Runbook-driven    │  │
                    │          │           │ Approval gates     │  │
                    │          │           └────────┬───────────┘  │
                    └──────────┼────────────────────┼─────────────┘
                               │                    │
                               ▼                    ▼
                    ┌─────────────────────────────────────────────┐
                    │            Core Library (tishift.core)       │
                    │                                             │
                    │  ┌─────────┐ ┌─────────┐ ┌─────────┐      │
                    │  │  scan   │ │ convert │ │  load   │      │
                    │  │ Assess  │ │ Schema  │ │ Bulk    │      │
                    │  │ Score   │ │ DDL     │ │ Import  │      │
                    │  │ Report  │ │ SP→Code │ │ DMS/    │      │
                    │  │ Cost    │ │ Query   │ │ Lightn. │      │
                    │  └────┬────┘ └────┬────┘ └────┬────┘      │
                    │       │           │           │            │
                    │  ┌────┴────┐ ┌────┴────┐                  │
                    │  │  sync   │ │  check  │                  │
                    │  │ CDC     │ │ Data    │                  │
                    │  │ Binlog  │ │ Diff    │                  │
                    │  │ DMS/DM  │ │ Row cmp │                  │
                    │  └────┬────┘ └────┬────┘                  │
                    │       │           │                        │
                    └───────┼───────────┼────────────────────────┘
                            │           │
                  ┌─────────▼───────────▼──────────┐
                  │      Shared Foundation          │
                  │  - Connection Pool (PyMySQL)    │
                  │  - Config (.yaml + pydantic)    │
                  │  - Structured JSON Logging      │
                  │  - Prometheus Metrics            │
                  │  - Progress Tracker              │
                  │  - Continuation Tokens           │
                  └────────────────────────────────┘
```

**Key design principle:** The core library has no knowledge of CLI or MCP. It exposes Python functions that return data structures. The CLI formats them for terminal. The MCP server exposes them as tools for Claude.

---

## Global: Shared Foundation

### Config File (`tishift.yaml`)

Every subcommand reads from one config file. The user creates this once.

```yaml
# tishift.yaml
source:
  host: aurora-cluster.xxxxx.us-east-1.rds.amazonaws.com
  port: 3306
  user: admin
  password: ${TISHIFT_SOURCE_PASSWORD}  # env var reference
  database: myapp  # or "*" for all databases

target:
  host: tidb-cluster.xxxxx.prod.aws.tidbcloud.com
  port: 4000
  user: root
  password: ${TISHIFT_TARGET_PASSWORD}
  database: myapp
  tls: true

aws:
  region: us-east-1
  profile: default  # optional, for DMS/CloudWatch access

ai:
  provider: claude  # or "none" to disable AI features
  api_key: ${ANTHROPIC_API_KEY}
  model: claude-sonnet-4-20250514

output:
  dir: ./tishift-reports
  formats: [cli, json, html]  # also supports: pdf, markdown

logging:
  level: info  # debug, info, warn, error
  file: tishift.log

metrics:
  enabled: true
  port: 9090  # Prometheus scrape endpoint
```

### Connection Manager

- Uses `PyMySQL` for both Aurora (source) and TiDB (target) since both speak MySQL protocol
- Connection pooling with configurable pool size
- Read-only mode for `scan` and `check` (enforced at connection level with `SET SESSION TRANSACTION READ ONLY`)
- Auto-retry with exponential backoff on transient connection errors
- SSL/TLS support for both source and target
- Password can come from: config file, env var, AWS Secrets Manager, or interactive prompt

### Logging & Progress

- Structured JSON logging (like CockroachDB's MOLT tools do — machine-parseable)
- Human-friendly CLI progress bars via `Rich` library
- Every long-running operation emits progress events: `{"type": "progress", "phase": "scan", "table": "orders", "pct": 45}`
- Prometheus metrics endpoint for monitoring long-running operations

### Installation

```bash
# Option 1: pip
pip install tishift

# Option 2: pipx (isolated)
pipx install tishift

# Option 3: single binary (PyInstaller)
curl -L https://github.com/pingcap/tishift/releases/latest/download/tishift-$(uname -s)-$(uname -m) -o tishift
chmod +x tishift

# Option 4: Docker
docker run -v $(pwd):/work pingcap/tishift scan --config /work/tishift.yaml
```

### Technology Stack

| Component | Library | Why |
|---|---|---|
| CLI framework | `click` | Subcommand routing, help generation, parameter validation |
| MCP server | `mcp[cli]` (FastMCP) | MCP tool registration, stdio/SSE transport, tool schemas |
| DB connection | `PyMySQL` | Pure Python MySQL client, works for both Aurora and TiDB |
| SQL parsing | `sqlglot` | Parse MySQL SQL into AST, transpile, analyze compatibility |
| CLI output | `Rich` | Tables, progress bars, colored output, tree views |
| HTML reports | `Jinja2` | Templated HTML report generation |
| PDF reports | `WeasyPrint` | Convert HTML to PDF for executive summaries |
| Config | `PyYAML` + `pydantic` | Config parsing with validation |
| Metrics | `prometheus_client` | Expose metrics for Grafana dashboards |
| AI integration | `anthropic` | Claude API for SP analysis and query rewriting |
| AWS integration | `boto3` | CloudWatch metrics, DMS automation, S3 access |
| Testing | `pytest` | Unit + integration tests |
| Packaging | `PyInstaller` | Single-binary distribution (CLI only) |

**Entry points in pyproject.toml:**
```toml
[project.scripts]
tishift = "tishift.cli:main"          # CLI entry point
tishift-mcp = "tishift.mcp:main"      # MCP server entry point
```

---

## Tool 1: `tishift scan`

### Purpose

Connects read-only to the customer's Aurora MySQL instance, performs comprehensive analysis, and produces a scored migration readiness report. No data leaves the customer's environment (unless AI features are enabled, in which case only schema metadata and SP code are sent to the AI API — never actual row data).

### Usage

```bash
# Basic scan
tishift scan --config tishift.yaml

# Scan specific database
tishift scan --config tishift.yaml --database myapp

# Scan with AI analysis of stored procedures
tishift scan --config tishift.yaml --ai

# Output only JSON (for piping to other tools)
tishift scan --config tishift.yaml --format json --quiet

# Scan with AWS cost analysis (needs boto3 credentials)
tishift scan --config tishift.yaml --cost-analysis
```

### Flags

| Flag | Default | Description |
|---|---|---|
| `--config` | `tishift.yaml` | Path to config file |
| `--database` | `*` (all) | Specific database to scan, or `*` for all |
| `--ai` | `false` | Enable AI-powered stored procedure analysis |
| `--cost-analysis` | `false` | Include Aurora cost estimation via CloudWatch |
| `--format` | `cli` | Output format: `cli`, `json`, `html`, `pdf`, `markdown`, or comma-separated |
| `--output-dir` | `./tishift-reports` | Where to write report files |
| `--quiet` | `false` | Suppress CLI output (for scripting) |
| `--include-query-log` | `false` | Parse performance_schema or slow query log for query compatibility |
| `--sample-rows` | `0` | Number of sample rows to inspect per table for data type edge cases |

### What It Collects

The scanner runs a series of **collectors**, each responsible for one category of metadata. All collectors use read-only queries only.

#### Collector 1: Schema Inventory

Queries `information_schema` to build a complete picture:

```python
# Tables
SELECT table_schema, table_name, engine, row_format, table_rows,
       data_length, index_length, auto_increment, table_collation,
       create_options
FROM information_schema.tables
WHERE table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')

# Columns
SELECT table_schema, table_name, column_name, ordinal_position,
       column_default, is_nullable, data_type, column_type,
       character_set_name, collation_name, column_key, extra,
       generation_expression
FROM information_schema.columns
WHERE table_schema NOT IN (...)

# Indexes
SELECT table_schema, table_name, index_name, non_unique, index_type,
       GROUP_CONCAT(column_name ORDER BY seq_in_index) as columns
FROM information_schema.statistics
WHERE table_schema NOT IN (...)
GROUP BY table_schema, table_name, index_name

# Foreign Keys
SELECT constraint_schema, table_name, constraint_name,
       referenced_table_schema, referenced_table_name,
       GROUP_CONCAT(column_name) as columns,
       GROUP_CONCAT(referenced_column_name) as ref_columns
FROM information_schema.key_column_usage
WHERE referenced_table_name IS NOT NULL

# Stored Procedures & Functions
SELECT routine_schema, routine_name, routine_type, data_type,
       routine_body, routine_definition, is_deterministic,
       security_type, definer
FROM information_schema.routines
WHERE routine_schema NOT IN (...)

# Triggers
SELECT trigger_schema, trigger_name, event_manipulation,
       event_object_table, action_statement, action_timing
FROM information_schema.triggers
WHERE trigger_schema NOT IN (...)

# Views
SELECT table_schema, table_name, view_definition, check_option,
       is_updatable, definer, security_type
FROM information_schema.views
WHERE table_schema NOT IN (...)

# Events (scheduled)
SELECT event_schema, event_name, event_type, execute_at,
       interval_value, interval_field, event_definition, status
FROM information_schema.events

# Partitions
SELECT table_schema, table_name, partition_name, partition_method,
       partition_expression, partition_description,
       subpartition_method, subpartition_expression
FROM information_schema.partitions
WHERE partition_name IS NOT NULL

# Character sets in use
SELECT DISTINCT character_set_name, collation_name,
       COUNT(*) as column_count
FROM information_schema.columns
WHERE table_schema NOT IN (...)
GROUP BY character_set_name, collation_name
```

#### Collector 2: Query Patterns (Optional — `--include-query-log`)

If the user enables this, scan `performance_schema.events_statements_summary_by_digest` for the top N queries by execution count and total time. Then use `sqlglot` to parse each query's AST and check for TiDB-incompatible constructs.

```python
SELECT digest_text, count_star, sum_timer_wait,
       sum_rows_affected, sum_rows_sent, sum_rows_examined
FROM performance_schema.events_statements_summary_by_digest
ORDER BY sum_timer_wait DESC
LIMIT 500
```

For each query, run through the `sqlglot` AST and flag:
- `XML_EXTRACT()`, `ExtractValue()`, `UpdateXML()` → unsupported, suggest JSON alternatives
- `SPATIAL` functions (`ST_Distance`, `ST_Within`, etc.) → unsupported
- `GET_LOCK()` / `RELEASE_LOCK()` → limited support in TiDB
- `SQL_CALC_FOUND_ROWS` → deprecated in MySQL 8.0, not optimized in TiDB
- `SELECT ... FOR UPDATE` with `NOWAIT` or `SKIP LOCKED` → check TiDB version support
- `XA START` / `XA END` / `XA PREPARE` / `XA COMMIT` → unsupported
- Nested subqueries in `UPDATE`/`DELETE` → may need rewrite for TiDB optimizer
- `GROUP BY` without aggregation on selected columns → TiDB strict mode differs from Aurora

#### Collector 3: Data Profile

```python
# Per-table sizing
SELECT table_schema, table_name, table_rows,
       ROUND(data_length / 1024 / 1024, 2) AS data_mb,
       ROUND(index_length / 1024 / 1024, 2) AS index_mb,
       ROUND((data_length + index_length) / 1024 / 1024, 2) AS total_mb
FROM information_schema.tables
WHERE table_schema NOT IN (...)
ORDER BY data_length + index_length DESC

# BLOB/TEXT column detection
SELECT table_schema, table_name, column_name, data_type
FROM information_schema.columns
WHERE data_type IN ('blob', 'mediumblob', 'longblob', 'text', 'mediumtext', 'longtext')
  AND table_schema NOT IN (...)

# Largest BLOB/TEXT values (sampled)
# For each table with BLOB/TEXT, run:
# SELECT MAX(LENGTH(blob_column)) FROM table LIMIT 1
```

#### Collector 4: Aurora-Specific Metadata

```python
# Aurora version detection
SELECT @@aurora_version, @@version, @@version_comment

# Binlog format (CRITICAL: must be ROW for CDC)
SELECT @@binlog_format, @@binlog_row_image

# Important server variables
SELECT @@character_set_server, @@collation_server,
       @@transaction_isolation, @@sql_mode,
       @@max_connections, @@innodb_buffer_pool_size,
       @@lower_case_table_names, @@explicit_defaults_for_timestamp
```

If `--cost-analysis` is enabled and AWS credentials are available:

```python
# Via boto3 CloudWatch
# Fetch: CPUUtilization, DatabaseConnections, FreeableMemory,
#         ReadIOPS, WriteIOPS, ReadLatency, WriteLatency,
#         VolumeBytesUsed, VolumeReadIOPs, VolumeWriteIOPs
# Over last 30 days, 1-hour granularity
# Calculate: avg ACU usage, peak ACU, storage size, total I/O ops
# Estimate monthly cost from these metrics
```

#### Collector 5: Stored Procedure Deep Analysis (Optional — `--ai`)

For each stored procedure and function, if `--ai` is enabled:

1. Extract the full `CREATE PROCEDURE` / `CREATE FUNCTION` definition
2. Use `sqlglot` to parse as much as possible locally
3. Compute a local complexity score:
   - Lines of code
   - Number of `CURSOR` declarations (hard to refactor)
   - Number of `PREPARE` / `EXECUTE` dynamic SQL calls
   - Number of temporary tables
   - Number of control flow statements (`IF`, `WHILE`, `LOOP`, `CASE`)
   - Nested procedure calls
   - Transaction management (`START TRANSACTION`, `COMMIT`, `ROLLBACK`, `SAVEPOINT`)
4. Send to Claude API with a prompt like:

```
Analyze this MySQL stored procedure for migration to TiDB (which does not support stored procedures).

Procedure:
{procedure_definition}

Respond in JSON with:
- difficulty: "trivial" | "simple" | "moderate" | "complex" | "requires_redesign"
- automation_pct: number (0-100, how much of this the AI can fully generate)
- summary: one-line description of what it does
- suggested_approach: how to refactor (move to app layer, use TiDB features, etc.)
- equivalent_code: { python: "...", go: "...", javascript: "..." }
- tidb_compatible_sql: any pure SQL portions that work in TiDB
- warnings: list of edge cases or gotchas
```

5. Combine local scoring + AI analysis into the final report

### Scoring Engine

The scanner produces a **Migration Readiness Score** from 0 to 100.

#### Scoring Methodology

Inspired by how mature migration tools score complexity (see Ora2Pg's scoring system in `lib/Ora2Pg/PLSQL.pm`), but adapted for Aurora → TiDB:

**Category weights:**

| Category | Weight | What's Measured |
|---|---|---|
| Schema Compatibility | 30% | How many schema objects are natively supported in TiDB |
| Data Complexity | 20% | Data size, BLOB usage, table count, largest table size |
| Query Compatibility | 20% | % of top queries that run unmodified on TiDB |
| Procedural Code | 20% | Stored procedures, triggers, events — effort to refactor |
| Operational Readiness | 10% | Binlog format, Aurora version, character sets |

**Scoring rules per category:**

Schema Compatibility (30 points max):
- Start at 30
- Subtract 0 for each standard table (InnoDB, utf8mb4, no SPs)
- Subtract 2 per stored procedure (up to -10)
- Subtract 2 per trigger (up to -10)
- Subtract 1 per foreign key constraint (up to -5, since TiDB partially supports)
- Subtract 3 if any spatial/GIS columns exist
- Subtract 2 if fulltext indexes are used
- Subtract 1 per unsupported collation
- Subtract 3 if XA transactions detected
- Subtract 1 per event/scheduler dependency

Data Complexity (20 points max):
- Start at 20
- Subtract 2 if total data > 500GB
- Subtract 5 if total data > 1TB
- Subtract 10 if total data > 5TB
- Subtract 2 if any single table > 100GB
- Subtract 1 per LONGBLOB column (up to -5)
- Subtract 2 if > 1000 tables

Query Compatibility (20 points max):
- Start at 20
- Only scored if `--include-query-log` is used, otherwise assume 18/20
- Subtract 1 per query using unsupported functions (up to -10)
- Subtract 2 if XA transaction patterns found
- Subtract 1 per GET_LOCK usage
- Subtract 2 if heavy use of SQL_CALC_FOUND_ROWS

Procedural Code (20 points max):
- Start at 20
- If zero stored procedures, triggers, events → keep 20
- Subtract 1 per trivial SP (< 10 lines, no cursors)
- Subtract 2 per simple SP (< 30 lines, no cursors)
- Subtract 3 per moderate SP (cursors, temp tables, < 100 lines)
- Subtract 5 per complex SP (dynamic SQL, nested calls, > 100 lines)
- Subtract 5 per SP that requires_redesign (assessed by AI or heuristic)
- Floor at 0

Operational Readiness (10 points max):
- Start at 10
- Subtract 5 if binlog_format is not ROW
- Subtract 2 if Aurora version is 2.x (MySQL 5.7 — approaching EOL)
- Subtract 1 if character_set_server is not utf8mb4
- Subtract 2 if lower_case_table_names differs between source and target

**Final Score Interpretation:**

| Score | Rating | Meaning |
|---|---|---|
| 90-100 | 🟢 Excellent | Near drop-in migration, minimal effort |
| 75-89 | 🟡 Good | Straightforward migration with some refactoring |
| 50-74 | 🟠 Moderate | Significant refactoring needed, but feasible |
| 25-49 | 🔴 Challenging | Major application changes required |
| 0-24 | ⛔ Difficult | Requires substantial redesign; discuss with PingCAP SA team |

**Automation Coverage Estimate:**

Instead of estimating person-days (since TiShift + AI handles most of the work), the scanner reports what percentage of the migration is fully automated vs what still needs human review.

```python
automation_report = {
    "fully_automated": {
        "pct": 85,  # calculated from objects below
        "includes": [
            "schema DDL conversion",
            "data type mapping",
            "collation conversion",
            "index recreation",
            "data transfer orchestration",
            "row-level validation",
            "CDC sync setup"
        ]
    },
    "ai_assisted": {
        "pct": 10,  # AI generates code, human reviews
        "includes": [
            "stored procedure → app code (AI-generated, needs review)",
            "trigger → middleware (AI-generated, needs review)",
            "complex query rewrites"
        ]
    },
    "manual_required": {
        "pct": 5,  # human must do this
        "includes": [
            "application connection string cutover",
            "SP integration into app codebase",
            "business logic validation",
            "performance tuning post-migration"
        ]
    },
    "estimated_clock_time": {
        "data_transfer": "~2 hours (89 GB at 100 Mbps)",
        "schema_conversion": "< 1 minute (automated)",
        "sp_conversion": "~30 seconds per SP (AI)",
        "validation": "~45 minutes (parallel row comparison)",
        "total_tool_runtime": "~3-4 hours",
        "human_review_estimate": "4-8 hours for AI-generated code review + integration"
    }
}
```

**How automation % is calculated:**

| Object Type | Automation Level | How |
|---|---|---|
| Standard tables (InnoDB, utf8mb4, no SPs) | 100% automated | `tishift convert` + `tishift load` |
| Tables with unsupported collations | 100% automated | `tishift convert` maps collations |
| Tables with foreign keys | 100% automated | DDL kept as-is (TiDB parses them) |
| Tables with fulltext indexes | 95% automated | Auto-removed or kept based on target |
| Stored procedures (trivial/simple) | 90% AI-assisted | AI generates code, human spot-checks |
| Stored procedures (moderate) | 70% AI-assisted | AI generates code, human reviews logic |
| Stored procedures (complex) | 50% AI-assisted | AI generates skeleton, human completes |
| Triggers | 80% AI-assisted | AI generates middleware, human integrates |
| Spatial/GIS columns | 30% manual | Tool flags and suggests alternatives |
| XA transactions | 10% manual | Requires application architecture redesign |
| Cutover | 0% manual | Human decision, tool provides checklist |

The scanner rolls these up into a single **automation coverage percentage** that answers the real question: "How much of this does TiShift handle for me?"

### Report Output

#### CLI Output (Rich)

```
╔═══════════════════════════════════════════════════════════════╗
║              TiShift — Migration Readiness Report             ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Source: aurora-prod.xxxxx.us-east-1.rds.amazonaws.com        ║
║  Aurora Version: 3.07.1 (MySQL 8.0.36)                        ║
║  Databases: 3 | Tables: 247 | Total Size: 89.3 GB             ║
║                                                               ║
║  ── Overall Score ─────────────────────────── 82/100 🟡 ──   ║
║                                                               ║
║  Schema Compatibility ............. 26/30  🟡                 ║
║  Data Complexity .................. 18/20  🟢                 ║
║  Query Compatibility .............. 16/20  🟡                 ║
║  Procedural Code .................. 12/20  🟠                 ║
║  Operational Readiness ............  10/10  🟢                ║
║                                                               ║
║  ── Issues Found ──────────────────────────────────────────   ║
║                                                               ║
║  ⛔ BLOCKERS: 0                                               ║
║  ⚠️  WARNINGS: 7                                              ║
║     • 4 stored procedures need refactoring                    ║
║       - get_customer_orders (90% AI-automated)                ║
║       - calc_monthly_report (50% AI-assisted, needs review)   ║
║       - sync_inventory (95% AI-automated)                     ║
║       - process_payment (50% AI-assisted, needs review)       ║
║     • 2 triggers → move to application layer                  ║
║     • 1 scheduled event → move to external scheduler          ║
║  ℹ️  INFO: 3                                                  ║
║     • 12 foreign keys (TiDB parses, partially enforces)       ║
║     • latin1 collation on 3 tables (recommend utf8mb4)        ║
║     • AUTO_INCREMENT gaps expected (non-sequential in TiDB)   ║
║                                                               ║
║  ── Estimates ─────────────────────────────────────────────   ║
║                                                               ║
║  Automation Coverage .......... 85% fully automated           ║
║  AI-Assisted (needs review) ... 10%                           ║
║  Manual Required .............. 5%                             ║
║  Tool Runtime ................. ~3-4 hours                     ║
║  Human Review ................. ~4-8 hours                     ║
║  Data Transfer Time ........... ~2 hours (at 100 Mbps)        ║
║  Current Aurora Cost .......... ~$1,847/month                  ║
║  Estimated TiDB Cloud Cost .... ~$1,150/month                 ║
║  Projected Savings ............ ~38%                           ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

Reports saved to: ./tishift-reports/
  • tishift-report-2026-02-19.json
  • tishift-report-2026-02-19.html
```

#### JSON Output Structure

```json
{
  "version": "1.0.0",
  "generated_at": "2026-02-19T15:30:00Z",
  "source": {
    "host": "aurora-prod.xxxxx.us-east-1.rds.amazonaws.com",
    "aurora_version": "3.07.1",
    "mysql_version": "8.0.36",
    "binlog_format": "ROW",
    "character_set": "utf8mb4",
    "collation": "utf8mb4_0900_ai_ci"
  },
  "summary": {
    "overall_score": 82,
    "rating": "good",
    "database_count": 3,
    "table_count": 247,
    "total_data_size_gb": 89.3,
    "total_index_size_gb": 22.1,
    "estimated_data_transfer_hours": 2.1,
    "automation_coverage_pct": 85,
    "ai_assisted_pct": 10,
    "manual_required_pct": 5,
    "estimated_tool_runtime_hours": 3.5,
    "estimated_human_review_hours": { "min": 4, "max": 8 }
  },
  "scores": {
    "schema_compatibility": { "score": 26, "max": 30 },
    "data_complexity": { "score": 18, "max": 20 },
    "query_compatibility": { "score": 16, "max": 20 },
    "procedural_code": { "score": 12, "max": 20 },
    "operational_readiness": { "score": 10, "max": 10 }
  },
  "issues": {
    "blockers": [],
    "warnings": [
      {
        "type": "stored_procedure",
        "object": "myapp.get_customer_orders",
        "severity": "warning",
        "difficulty": "moderate",
        "automation_pct": 70,
        "message": "Stored procedure uses cursors and temp tables; AI will generate application code, human review recommended",
        "ai_suggestion": "Move to Python/Go function. Core logic is a JOIN with aggregation — can be a single TiDB query."
      }
    ],
    "info": []
  },
  "schema_details": {
    "databases": [...],
    "tables": [...],
    "stored_procedures": [...],
    "triggers": [...],
    "views": [...],
    "foreign_keys": [...],
    "indexes": [...]
  },
  "data_profile": {
    "largest_tables": [...],
    "blob_columns": [...],
    "total_row_count": 45000000
  },
  "cost_analysis": {
    "aurora_monthly_estimate": 1847.00,
    "tidb_monthly_estimate": 1150.00,
    "savings_pct": 37.7,
    "aurora_breakdown": { "compute": 1200, "storage": 447, "io": 200 },
    "tidb_recommendation": { "tier": "Dedicated", "nodes": 3, "vcpu": 8, "ram_gb": 32, "storage_gb": 200 }
  }
}
```

#### HTML Report

The HTML report uses Jinja2 templates and should be self-contained (inline CSS, no external dependencies) so it can be opened in any browser or emailed. It should include:

- Executive summary section with the score gauge (SVG)
- Expandable/collapsible sections for each analysis category
- Table of all stored procedures with difficulty ratings and AI suggestions
- Interactive data size chart (inline SVG bar chart)
- Cost comparison table
- Remediation checklist with checkboxes
- Print-friendly layout

#### PDF Report

Generate from the HTML using WeasyPrint. Two versions:
- Executive summary (2-3 pages, for decision-makers)
- Full technical report (all details)

---

## Tool 2: `tishift convert`

### Purpose

Takes the scan results and generates TiDB-compatible schema DDL, rewrites stored procedures into application code, and produces ready-to-execute migration scripts.

### Usage

```bash
# Convert schema from scan results
tishift convert --config tishift.yaml --scan-report ./tishift-reports/report.json

# Convert just stored procedures with AI
tishift convert --config tishift.yaml --scan-report ./report.json --sp-only --ai --language python

# Convert and apply directly to target TiDB
tishift convert --config tishift.yaml --scan-report ./report.json --apply

# Dry run — show what would change without applying
tishift convert --config tishift.yaml --scan-report ./report.json --dry-run
```

### Flags

| Flag | Default | Description |
|---|---|---|
| `--scan-report` | Required | Path to JSON report from `tishift scan` |
| `--sp-only` | `false` | Only convert stored procedures, skip schema |
| `--schema-only` | `false` | Only convert schema DDL, skip stored procedures |
| `--ai` | `false` | Use Claude API for stored procedure refactoring |
| `--language` | `python` | Target language for SP conversion: `python`, `go`, `java`, `javascript` |
| `--apply` | `false` | Execute converted DDL against target TiDB |
| `--dry-run` | `false` | Show diff of what would change |
| `--output-dir` | `./tishift-convert/` | Where to write output files |

### Schema Conversion Rules

The converter applies these transformations in order:

**1. Engine normalization:**
- Any non-InnoDB engine → InnoDB (TiDB only supports InnoDB)

**2. Character set / collation:**
- `latin1` → keep (TiDB supports it) but add a comment recommending `utf8mb4`
- Unsupported collations → map to nearest TiDB-supported collation
- Default: `utf8mb4_bin` or `utf8mb4_general_ci`

**3. AUTO_INCREMENT:**
- Keep AUTO_INCREMENT syntax (TiDB supports it)
- Add comment: `/* TiShift: AUTO_INCREMENT values will be unique but not sequential in TiDB */`
- If scan detected app depends on sequential ordering, flag for manual review
- Suggest `AUTO_RANDOM` for primary keys that don't need sequential values (reduces hotspots)

**4. Foreign keys:**
- Keep in DDL (TiDB parses them, partially enforces since v6.6)
- Add comment noting enforcement behavior differences
- Suggest application-layer constraint validation as belt-and-suspenders

**5. Fulltext indexes:**
- If target is TiDB Cloud Starter/Essential: keep
- If target is TiDB self-hosted: remove and suggest external search (Elasticsearch, MeiliSearch)
- Add comment with alternatives

**6. Spatial columns/indexes:**
- Remove spatial indexes
- Convert spatial columns to JSON or TEXT with a migration note
- Flag for manual review

**7. Partitioning:**
- RANGE, LIST, HASH, KEY → keep (TiDB supports these)
- Adjust syntax differences if any
- Range COLUMNS → verify TiDB support for the specific column type

**8. Generated columns:**
- Virtual → verify TiDB support (supported but with limitations)
- Stored → keep (supported)

**9. Views:**
- Parse view definitions with `sqlglot`
- Flag views using unsupported functions
- Rewrite where possible

**10. Events:**
- Generate external scheduler equivalent (cron job, Kubernetes CronJob, or cloud scheduler)
- Output as separate script

### Stored Procedure Conversion

For each stored procedure/function:

**Without AI (`--ai` not set):**
1. Parse the SP body with `sqlglot` where possible
2. Extract the core SQL statements
3. Generate a skeleton in the target language with:
   - Function signature matching the SP's parameters
   - Raw SQL strings for each statement
   - Transaction management boilerplate
   - Cursor-to-loop conversion (basic template)
   - Comments where manual work is needed

**With AI (`--ai` set):**
1. Send full SP definition to Claude with structured prompt
2. Get back production-quality application code
3. Include error handling, connection pooling usage, and test stubs
4. Generate both the application code AND the equivalent TiDB-compatible SQL

### Output Structure

```
tishift-convert/
├── schema/
│   ├── 01-create-tables.sql          # All CREATE TABLE statements, TiDB-compatible
│   ├── 02-create-indexes.sql          # Secondary indexes (applied after data load for speed)
│   ├── 03-create-views.sql            # Views, with flagged/rewritten ones
│   ├── 04-foreign-keys.sql            # FK constraints (applied last)
│   └── conversion-notes.md            # Human-readable notes on all changes made
├── procedures/
│   ├── get_customer_orders.py         # Converted SP → Python
│   ├── get_customer_orders.go         # Same SP → Go
│   ├── get_customer_orders_test.py    # Generated test stub
│   └── README.md                      # Mapping of old SPs to new code
├── triggers/
│   ├── after_order_insert.py          # Trigger logic as app middleware
│   └── README.md                      # How to integrate trigger replacements
├── events/
│   ├── daily_cleanup.cron             # Cron equivalent
│   └── README.md
├── diff/
│   ├── schema-diff.sql                # Side-by-side: Aurora original vs TiDB converted
│   └── schema-diff.html               # Visual diff report
└── apply.sh                           # Script to execute all DDL against TiDB in correct order
```

---

## Tool 3: `tishift load`

### Purpose

Performs the initial bulk data load from Aurora MySQL to TiDB. Chooses the optimal strategy based on data size.

### Usage

```bash
# Auto-detect best strategy based on data size
tishift load --config tishift.yaml

# Force DMS strategy
tishift load --config tishift.yaml --strategy dms

# Force Lightning strategy (requires S3 intermediate)
tishift load --config tishift.yaml --strategy lightning --s3-bucket my-migration-bucket

# Load specific tables only
tishift load --config tishift.yaml --tables "orders,customers,products"

# Resume a failed load
tishift load --config tishift.yaml --resume --continuation-token abc123
```

### Strategy Selection

| Data Size | Strategy | How It Works |
|---|---|---|
| < 100 GB | Direct `LOAD DATA` | Export with `mysqldump` → import via MySQL protocol |
| 100 GB – 1 TB | AWS DMS | Full load task, Aurora source → TiDB target (MySQL endpoint) |
| > 1 TB | TiDB Lightning | Aurora snapshot → S3 export → TiDB Lightning physical import |

### DMS Strategy Details

When using DMS:
1. Create DMS replication instance (or use existing)
2. Create source endpoint (Aurora MySQL)
3. Create target endpoint (TiDB, configured as MySQL-compatible, port 4000)
4. Create migration task: full-load mode
5. Configure table mappings from scan report
6. Configure LOB settings based on BLOB/TEXT analysis from scan
7. Monitor task progress, log errors
8. Output continuation token for resumability

All DMS operations are automated via `boto3`. The user needs appropriate IAM permissions.

### Lightning Strategy Details

When using Lightning:
1. Export Aurora snapshot to S3 (via `aws rds export-task`)
2. Download/convert to CSV or SQL format Lightning can ingest
3. Configure TiDB Lightning with physical import mode
4. Run Lightning, monitor progress
5. Run `ADMIN CHECK TABLE` on imported tables
6. Output continuation token

### Resumability

Every load operation emits a **continuation token** — a JSON blob tracking which tables/partitions/shards have been loaded. If the load fails or is interrupted, re-running with `--resume --continuation-token <token>` skips already-completed work.

### Parallelism

- Tables are loaded concurrently (configurable `--concurrency`, default 4)
- Large tables are sharded by primary key ranges and loaded in parallel
- Progress emitted per-table and per-shard

### Flags

| Flag | Default | Description |
|---|---|---|
| `--strategy` | `auto` | Load strategy: `auto`, `direct`, `dms`, `lightning` |
| `--concurrency` | `4` | Number of tables to load in parallel |
| `--tables` | `*` | Comma-separated list of tables, or `*` for all |
| `--exclude-tables` | none | Tables to skip |
| `--s3-bucket` | none | S3 bucket for Lightning intermediate storage |
| `--dms-instance-class` | `dms.r5.large` | DMS replication instance class |
| `--resume` | `false` | Resume from continuation token |
| `--continuation-token` | none | Token from previous run |
| `--schema-first` | `true` | Apply schema DDL before loading data |
| `--drop-indexes` | `true` | Drop secondary indexes before load, recreate after (faster) |

---

## Tool 4: `tishift sync`

### Purpose

After the initial bulk load, keeps Aurora and TiDB in sync via CDC (Change Data Capture) using binlog replication. This enables a gradual cutover where both databases are live.

### Usage

```bash
# Start CDC replication from Aurora to TiDB
tishift sync --config tishift.yaml

# Start from a specific binlog position (from load output)
tishift sync --config tishift.yaml --start-position "mysql-bin.000123:4567"

# Start from DMS CDC cursor
tishift sync --config tishift.yaml --strategy dms --dms-task-arn arn:aws:dms:...

# Monitor sync lag
tishift sync --config tishift.yaml --status
```

### Strategies

| Strategy | Backend | Best For |
|---|---|---|
| `dms` | AWS DMS CDC task | When already using DMS for initial load; AWS-managed |
| `dm` | TiDB Data Migration | When using TiDB's native tooling; more control |

### DMS CDC Mode

1. Modify existing DMS task to enable CDC (or create new CDC-only task)
2. Start from the checkpoint recorded during `tishift load`
3. Monitor replication lag via CloudWatch
4. Emit lag metrics to Prometheus endpoint

### TiDB DM Mode

1. Generate DM task configuration YAML
2. Deploy DM worker (or configure existing DM cluster)
3. Start incremental replication from recorded binlog position
4. Monitor via DM dashboard

### Sync Status Output

```json
{
  "strategy": "dms",
  "status": "replicating",
  "source_binlog_position": "mysql-bin.000156:89012",
  "target_applied_position": "mysql-bin.000156:88990",
  "lag_seconds": 0.3,
  "tables_syncing": 247,
  "errors": 0,
  "started_at": "2026-02-19T10:00:00Z",
  "uptime_hours": 48.5
}
```

### Flags

| Flag | Default | Description |
|---|---|---|
| `--strategy` | `dms` | Sync backend: `dms` or `dm` |
| `--start-position` | auto | Binlog position to start from |
| `--dms-task-arn` | none | Existing DMS task to modify for CDC |
| `--status` | `false` | Show current sync status and exit |
| `--stop` | `false` | Stop sync gracefully |

---

## Tool 5: `tishift check`

### Purpose

Validates that data in TiDB matches the source Aurora MySQL — row by row, column by column. Run this after `load` and/or during `sync` to build confidence before cutover.

This is the safety net. Without it, you're flying blind.

### Usage

```bash
# Full validation (structure + data)
tishift check --config tishift.yaml

# Schema-only validation (fast)
tishift check --config tishift.yaml --schema-only

# Specific tables
tishift check --config tishift.yaml --tables "orders,customers"

# Row-level check with sampling (faster for huge tables)
tishift check --config tishift.yaml --sample-rate 0.01

# Continuous validation during sync (re-checks every N minutes)
tishift check --config tishift.yaml --continuous --interval 300
```

### What It Validates

#### Level 1: Table Structure

- Source and target have the same tables
- Flag missing tables on target (data not migrated yet)
- Flag extraneous tables on target (shouldn't exist)

#### Level 2: Column Definitions

For each table that exists on both sides:
- Compare column names, order, data types, nullability, defaults
- Flag type mismatches (e.g., AUTO_INCREMENT behavior differences)
- Track "conditional matches" — columns where types differ but data is still comparable (e.g., `INT AUTO_INCREMENT` on Aurora vs `BIGINT AUTO_RANDOM` on TiDB)

#### Level 3: Row-Level Data

For each table:
1. Count rows on source and target — flag if different
2. Compute checksum on primary key column(s) to detect drift
3. Page through data in batches (default 20,000 rows per batch, configurable)
4. For each batch, compare row-by-row:
   - Select rows ordered by primary key from both source and target
   - Hash each row's values
   - Track: matched, missing on target, missing on source (extraneous), mismatched values
5. For mismatched rows, identify which columns differ

#### Level 4: Row Count Reconciliation

Quick sanity check for large tables where full row comparison is too slow:
- `SELECT COUNT(*) FROM table` on both sides
- If counts match, flag as "count_verified"
- If counts differ, report the delta

#### Level 5: Checksum Verification

For each table:
- `CHECKSUM TABLE table_name` on both sides (if supported)
- Or compute `MD5(CONCAT_WS(',', col1, col2, ...))` for a sample of rows

### Output

```json
{
  "version": "1.0.0",
  "checked_at": "2026-02-19T18:00:00Z",
  "duration_seconds": 342,
  "summary": {
    "tables_checked": 247,
    "tables_matching": 244,
    "tables_with_issues": 3,
    "total_rows_checked": 45000000,
    "total_rows_matching": 44999847,
    "total_rows_missing": 150,
    "total_rows_mismatched": 3,
    "total_rows_extraneous": 0
  },
  "tables": [
    {
      "schema": "myapp",
      "table": "orders",
      "status": "verified",
      "source_row_count": 12500000,
      "target_row_count": 12500000,
      "rows_matching": 12500000,
      "rows_missing": 0,
      "rows_mismatched": 0,
      "rows_extraneous": 0,
      "column_mismatches": [],
      "conditional_matches": 0,
      "duration_seconds": 45
    },
    {
      "schema": "myapp",
      "table": "audit_log",
      "status": "issues_found",
      "source_row_count": 8500000,
      "target_row_count": 8499850,
      "rows_matching": 8499847,
      "rows_missing": 150,
      "rows_mismatched": 3,
      "rows_extraneous": 0,
      "column_mismatches": [
        {
          "column": "id",
          "source_type": "BIGINT AUTO_INCREMENT",
          "target_type": "BIGINT AUTO_RANDOM",
          "impact": "conditional_match",
          "note": "Values differ due to AUTO_RANDOM but other columns match"
        }
      ],
      "conditional_matches": 3,
      "missing_sample": [
        {"id": 8499851, "table_name": "orders", "action": "INSERT"},
        {"id": 8499852, "table_name": "orders", "action": "UPDATE"}
      ],
      "duration_seconds": 38
    }
  ]
}
```

### Parallel Execution

- Multiple tables verified concurrently (`--concurrency`, default 16)
- Each table can be split into shards by primary key range for parallel comparison
- Progress bars per table in CLI mode

### Continuous Mode

With `--continuous --interval 300`, the checker:
1. Runs a full check
2. Waits N seconds
3. Re-runs, but only checks tables that had issues or that have been recently modified (via binlog position tracking or row count delta)
4. Outputs a running summary to both CLI and Prometheus metrics
5. Useful during the `sync` phase to build confidence before cutover

### Flags

| Flag | Default | Description |
|---|---|---|
| `--schema-only` | `false` | Only compare table structures, skip row data |
| `--tables` | `*` | Comma-separated table list |
| `--exclude-tables` | none | Tables to skip |
| `--concurrency` | `16` | Parallel table verification threads |
| `--row-batch-size` | `20000` | Rows per comparison batch |
| `--sample-rate` | `1.0` | Fraction of rows to check (0.01 = 1% sample) |
| `--continuous` | `false` | Keep running and re-checking |
| `--interval` | `300` | Seconds between checks in continuous mode |
| `--fail-on-mismatch` | `false` | Exit with non-zero code if any mismatches found (for CI/CD) |
| `--output` | `cli,json` | Output formats |

---

## TiDB Compatibility Rules Reference

These are the rules `tishift scan` and `tishift convert` use to assess and transform Aurora MySQL schemas.

### Blockers (Must Fix Before Migration)

| Feature | Aurora MySQL | TiDB | Scanner Action | Converter Action |
|---|---|---|---|---|
| Stored Procedures | Full support | Not supported | Flag + score impact | Generate app code |
| Triggers | Full support | Not supported | Flag + score impact | Generate app middleware |
| User-Defined Functions (UDF) | Full support | Not supported | Flag + score impact | Generate app function |
| Spatial/GIS types | Full support | Not supported | Block if critical | Convert to JSON/TEXT |
| XML functions | Supported | Not supported | Flag + score impact | Suggest JSON equivalent |
| XA Transactions | Supported | Not supported | Flag + score impact | Suggest redesign |
| Scheduled Events | Full support | Not supported | Flag | Generate cron/CronJob |

### Warnings (Works, But Differently)

| Feature | Aurora MySQL | TiDB | Scanner Action | Converter Action |
|---|---|---|---|---|
| Foreign Keys | Enforced | Parsed, partially enforced (v6.6+) | Warn | Keep DDL, add comment |
| Fulltext Indexes | Full support | Limited (Cloud only) | Warn | Keep or remove based on target |
| GET_LOCK / RELEASE_LOCK | Full support | Limited | Warn if used | Suggest Redis alternative |
| AUTO_INCREMENT | Sequential, no gaps | Unique, not sequential | Warn if app depends on order | Add comment, suggest AUTO_RANDOM |
| SQL_CALC_FOUND_ROWS | Supported | Supported but not optimized | Warn | Suggest `COUNT(*)` alternative |
| Temporary Tables in SP | Supported | Supported in sessions, not in SPs | Warn | Refactor as part of SP conversion |
| SAVEPOINT | Supported | Supported (pessimistic mode only) | Warn if optimistic mode is target | Add comment |
| GROUP BY behavior | ONLY_FULL_GROUP_BY depends on sql_mode | Strict by default | Info | Adjust queries |

### Compatible (No Action Needed)

| Feature | Notes |
|---|---|
| InnoDB storage engine | TiDB only engine, transparent |
| JSON data type | Fully supported |
| ENUM, SET | Supported |
| utf8mb4 | Default in TiDB |
| latin1 | Supported (recommend migrating to utf8mb4) |
| Window functions | Supported |
| CTEs | Supported |
| Prepared statements | Supported |
| Pessimistic transactions | Default mode in TiDB |
| RANGE/LIST/HASH/KEY partitioning | Supported with minor differences |
| Online DDL | TiDB handles DDL differently (distributed) but syntax compatible |

---

## Migration Workflow: End-to-End

### Path A: CLI (Production)

```
Step 1: ASSESS
┌─────────────────────────────────┐
│ tishift scan --config tishift.yaml --ai --cost-analysis
│                                 │
│ → Produces readiness report     │
│ → Score: 82/100                 │
│ → Automation: 85% auto, 10% AI  │
│ → Tool runtime: ~3-4 hours      │
│ → Cost savings: 38%             │
│ → 4 SPs need refactoring        │
└────────────────┬────────────────┘
                 │
Step 2: CONVERT  ▼
┌─────────────────────────────────┐
│ tishift convert --scan-report report.json --ai
│                                 │
│ → TiDB-compatible DDL scripts   │
│ → SP → Python/Go application    │
│ → Trigger → app middleware code │
│ → Visual schema diff            │
└────────────────┬────────────────┘
                 │
Step 3: LOAD     ▼
┌─────────────────────────────────┐
│ tishift load --config tishift.yaml
│                                 │
│ → Applies schema to TiDB       │
│ → Bulk loads data (DMS or       │
│   Lightning based on size)      │
│ → Records binlog position       │
└────────────────┬────────────────┘
                 │
Step 4: VALIDATE ▼
┌─────────────────────────────────┐
│ tishift check --config tishift.yaml
│                                 │
│ → Verifies all tables exist     │
│ → Compares row counts           │
│ → Row-level data comparison     │
│ → Reports mismatches            │
└────────────────┬────────────────┘
                 │
Step 5: SYNC     ▼
┌─────────────────────────────────┐
│ tishift sync --config tishift.yaml
│                                 │
│ → CDC replication starts        │
│ → Aurora writes flow to TiDB    │
│ → Continuous sync until cutover │
│                                 │
│ + tishift check --continuous    │
│   (validates during sync)       │
└────────────────┬────────────────┘
                 │
Step 6: CUTOVER  ▼
┌─────────────────────────────────┐
│ Manual step:                    │
│ 1. Stop application writes      │
│ 2. Wait for sync lag → 0        │
│ 3. tishift check (final)        │
│ 4. Switch app connection string  │
│    to TiDB (port 4000)          │
│ 5. tishift sync --stop          │
│ 6. Resume application writes    │
└─────────────────────────────────┘
```

### Path B: MCP (Conversational)

Same steps, same core logic, but Claude is the operator.

```
User: [attaches migration runbook] Start Phase 1 assessment.

Claude: Scanning your Aurora schema...
        [calls: scan_schema → assess_compatibility → profile_data]
        
        Found 47 tables, 4 SPs, 2 triggers. Score: 82/100.
        Automation coverage: 85%. 4 SPs need AI conversion.
        
        ⏸ CHECKPOINT — Want to see the full report, or proceed to conversion?

User: Generate the report, then convert.

Claude: [calls: generate_report → convert_schema → convert_stored_procedure × 4]
        
        Schema converted. Key changes:
        - 2 FULLTEXT indexes removed
        - stores.location POINT → JSON
        
        The calc_monthly_report SP was complex. Here's the Python code — 
        want to review it before I apply?

User: Looks good. Apply and start loading.

Claude: Applying schema to TiDB...
        [calls: apply_schema] ✓ 47 tables created
        
        Loading data. Starting with reference tables...
        [calls: load_table × N with progress updates]
        
        ⏸ CHECKPOINT — All tables loaded. Row counts match. Start CDC sync?

User: Yes, start sync.

Claude: [calls: start_sync]
        Replication running. Current lag: 2.3 seconds...
        [calls: check_sync_status periodically]
        Lag stable at < 0.5 seconds. Ready for cutover whenever you are.

User: Let's cut over.

Claude: Cutover checklist:
        1. ⬜ Stop application writes to Aurora
        2. ⬜ Wait for replication lag → 0
        3. ⬜ Final validation pass
        4. ⬜ Switch connection strings to TiDB
        5. ⬜ Stop CDC replication
        
        Tell me when you've stopped writes and I'll monitor the drain.
```
```

---

## MCP Server Interface

The MCP server wraps the same core library as the CLI, but exposes it as tools that Claude (or any MCP client) can call conversationally.

### Installation

```json
{
  "mcpServers": {
    "tishift": {
      "command": "uvx",
      "args": ["tishift-mcp"],
      "env": {
        "TISHIFT_CONFIG": "/path/to/tishift.yaml"
      }
    }
  }
}
```

The MCP server reads the same `tishift.yaml` config file as the CLI. No separate configuration needed.

### MCP Tools

The server exposes 12 tools, each mapping to a core library function:

#### Read-Only Tools (safe, no approval needed)

| Tool | Core Function | Description |
|---|---|---|
| `scan_schema` | `core.scan.collect_schema()` | Lists all tables, columns, indexes, SPs, triggers from Aurora |
| `assess_compatibility` | `core.scan.assess()` | Runs TiDB compatibility rules, returns scored report |
| `profile_data` | `core.scan.profile()` | Table sizes, row counts, BLOB detection, data distribution |
| `check_sync_status` | `core.sync.get_status()` | Returns replication lag, throughput, position |
| `validate_table` | `core.check.validate_table()` | Row count + checksum comparison for one table |
| `validate_rows` | `core.check.validate_rows()` | Deep row-by-row comparison (batched, parallel) |

#### Compute Tools (generate output, no DB writes)

| Tool | Core Function | Description |
|---|---|---|
| `convert_schema` | `core.convert.transform_schema()` | Aurora DDL → TiDB DDL, returns SQL + diff |
| `convert_stored_procedure` | `core.convert.transform_sp()` | SP → application code (Python/Go/Java/JS) |
| `generate_report` | `core.scan.generate_report()` | Produces HTML/PDF readiness report |

#### Write Tools (require explicit user approval in conversation)

| Tool | Core Function | Description |
|---|---|---|
| `apply_schema` | `core.convert.apply()` | Executes converted DDL on TiDB target |
| `load_table` | `core.load.load_table()` | Bulk loads one table from Aurora → TiDB |
| `start_sync` | `core.sync.start()` | Starts CDC replication (DMS or TiDB DM) |

### Security Model

The MCP server has strict safety boundaries:

```
READ-ONLY TOOLS ──────► No approval needed. Claude can call freely.
                         These never modify either database.

COMPUTE TOOLS ────────► No approval needed. These generate output
                         (SQL, code, reports) but don't execute anything.

WRITE TOOLS ──────────► REQUIRE explicit user approval in conversation.
                         Claude must show exactly what will be executed
                         and wait for "yes" before proceeding.
                         These are the only tools that modify the target DB.

SOURCE DATABASE ──────► NEVER written to. All source connections are
                         read-only. The MCP server enforces this at the
                         connection level (SELECT only).
```

Additional protections:
- All write operations target TiDB only, never Aurora source
- `--dry-run` mode available: write tools return what they *would* do without executing
- Every tool call is logged with timestamp, parameters, and result to `tishift-mcp-audit.jsonl`
- Connection credentials come from `tishift.yaml` or env vars, never passed through Claude

### Migration Runbook (Markdown-Driven Orchestration)

The recommended way to use TiShift MCP is with a **migration runbook** — a markdown file that acts as the playbook. The user attaches it to the conversation, and Claude follows it step by step, stopping for approval at marked checkpoints.

#### Template Runbook

```markdown
# Migration Runbook: [database_name] (Aurora MySQL → TiDB)

## Source
- Aurora MySQL version: [version]
- Cluster: [endpoint]
- Database: [database_name]
- Estimated size: [size]

## Target
- TiDB Cloud Dedicated (or self-hosted)
- Cluster: [endpoint]

## Phase 1: Assessment
1. Scan the source schema and profile all tables
2. Run compatibility assessment
3. Generate readiness report with automation coverage score
4. **CHECKPOINT** — Present findings. Wait for human review.

## Phase 2: Schema Conversion
5. Convert all table DDL to TiDB-compatible format
6. For each stored procedure, generate application code replacement
7. Show the schema diff (before/after) for review
8. **CHECKPOINT** — Wait for human approval before applying to target.

## Phase 3: Apply Schema & Load Data
9. Apply converted schema to TiDB target
10. Load tables in dependency order (reference tables first, large tables last)
11. Load large tables in parallel (configurable concurrency)
12. Validate row counts after each table completes
13. **CHECKPOINT** — Present load summary. Wait for human verification.

## Phase 4: Sync & Validate
14. Start CDC replication from Aurora → TiDB
15. Monitor sync lag until < 1 second sustained
16. Run deep row-level validation on all tables
17. Generate final migration report
18. **CHECKPOINT** — Present validation results. Ready for cutover decision.

## Phase 5: Cutover (Manual)
19. Human stops application writes to Aurora
20. Wait for replication to drain (lag = 0)
21. Final validation pass
22. Human switches application connection strings to TiDB
23. Human stops CDC replication

## Rules
- Never modify the source database
- Skip tables: [list any tables to exclude]
- Convert stored procedures to: [Python/Go/Java/JavaScript]
- If any validation fails, stop immediately and report
- For tables > 50GB, use TiDB Lightning
```

#### How It Works

1. **User** attaches the runbook to a conversation with Claude
2. **User** says: "Start Phase 1" (or "Run the full migration")
3. **Claude** reads the runbook, calls read-only tools (scan, assess, profile)
4. **Claude** presents findings in plain language
5. **Claude** stops at **CHECKPOINT** and waits for approval
6. **User** reviews, asks questions, says "continue"
7. **Claude** proceeds to next phase, calling write tools only after confirmation
8. Repeat until migration is complete

The runbook is the contract between the user and Claude. It defines what gets done, in what order, with what safety stops. Claude doesn't improvise — it follows the playbook.

### MCP vs CLI: When to Use Each

| Scenario | Use CLI | Use MCP |
|---|---|---|
| Production migration at enterprise | ✅ Deterministic, scriptable, auditable | ❌ Too much risk for AI interpretation |
| Partner demo / sales engineering | ❌ Not impressive in a meeting | ✅ Conversational, visual, WOW factor |
| First-time exploration / POC | ❌ Steep learning curve | ✅ Claude explains as it goes |
| CI/CD pipeline integration | ✅ Script it, cron it, forget it | ❌ MCP needs a conversation |
| Small team, no DBA | ❌ Need to read docs | ✅ Claude is the DBA |
| Compliance / change advisory board | ✅ Show exact commands | ❌ "AI decided" won't pass audit |
| Running on bastion host / EC2 | ✅ CLI runs anywhere | ❌ MCP needs local Claude session |
| Iterative debugging of conversion | ❌ Run, check, edit, repeat | ✅ "That SP conversion looks wrong, fix the error handling" |

### Audit Log

Every MCP tool call is appended to `tishift-mcp-audit.jsonl`:

```json
{
  "timestamp": "2025-03-15T14:32:01Z",
  "tool": "apply_schema",
  "category": "write",
  "approved_by_user": true,
  "parameters": {
    "tables": ["users", "products", "orders"],
    "dry_run": false
  },
  "result": {
    "status": "success",
    "tables_created": 47,
    "duration_seconds": 3.2
  }
}
```

This gives teams an audit trail even when using the conversational interface. The log can be attached to change requests as evidence of what was executed.

---

## Project Structure

```
tishift/
├── pyproject.toml                  # Package config, dependencies, entry points
├── README.md                       #   [project.scripts]
├── LICENSE                         #   tishift = "tishift.cli:main"
├── Dockerfile                      #   tishift-mcp = "tishift.mcp:main"
├── tishift/
│   ├── __init__.py
│   ├── cli.py                     # Click CLI entry point, subcommand routing
│   ├── mcp.py                     # FastMCP server entry point, tool registration
│   ├── config.py                  # Config loading, validation (pydantic)
│   ├── connection.py              # Connection pool manager (source + target)
│   ├── metrics.py                 # Prometheus metrics setup
│   ├── progress.py                # Rich progress bars and structured logging
│   ├── audit.py                   # MCP audit log writer (tishift-mcp-audit.jsonl)
│   │
│   ├── core/                      # Core library — NO knowledge of CLI or MCP
│   │   ├── __init__.py            # Public API: scan(), convert(), load(), sync(), check()
│   │   │
│   │   ├── scan/                  # Core scan logic
│   │   │   ├── __init__.py
│   │   │   ├── collectors/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── schema.py          # Schema inventory collector
│   │   │   │   ├── queries.py         # Query pattern collector
│   │   │   │   ├── data_profile.py    # Data sizing collector
│   │   │   │   ├── aurora.py          # Aurora-specific metadata
│   │   │   │   └── cloudwatch.py      # AWS CloudWatch cost metrics
│   │   │   ├── analyzers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── compatibility.py   # TiDB compatibility rule engine
│   │   │   │   ├── scoring.py         # Migration readiness scoring
│   │   │   │   ├── automation.py      # Automation coverage calculator
│   │   │   │   ├── cost.py            # Cost comparison (Aurora vs TiDB)
│   │   │   │   └── ai_analyzer.py     # Claude API SP analysis
│   │   │   └── reporters/
│   │   │       ├── __init__.py
│   │   │       ├── json_report.py     # JSON export (used by both CLI and MCP)
│   │   │       ├── html_report.py     # Jinja2 HTML report
│   │   │       ├── pdf_report.py      # WeasyPrint PDF
│   │   │       └── templates/
│   │   │           ├── report.html.j2
│   │   │           ├── executive.html.j2
│   │   │           └── styles.css
│   │   │
│   │   ├── convert/               # Core convert logic
│   │   │   ├── __init__.py
│   │   │   ├── schema_transformer.py  # DDL conversion rules
│   │   │   ├── sp_converter.py        # Stored procedure → application code
│   │   │   ├── trigger_converter.py   # Trigger → middleware code
│   │   │   ├── event_converter.py     # Event → cron/CronJob
│   │   │   ├── query_rewriter.py      # SQL query compatibility rewriting
│   │   │   ├── diff_generator.py      # Before/after schema diff
│   │   │   └── templates/
│   │   │       ├── sp_python.py.j2
│   │   │       ├── sp_go.go.j2
│   │   │       ├── sp_java.java.j2
│   │   │       ├── sp_javascript.js.j2
│   │   │       └── trigger_middleware.py.j2
│   │   │
│   │   ├── load/                  # Core load logic
│   │   │   ├── __init__.py
│   │   │   ├── strategy.py            # Auto-select load strategy
│   │   │   ├── direct_loader.py       # mysqldump + LOAD DATA
│   │   │   ├── dms_loader.py          # AWS DMS full-load automation
│   │   │   ├── lightning_loader.py    # TiDB Lightning orchestration
│   │   │   └── continuation.py        # Resume/checkpoint management
│   │   │
│   │   ├── sync/                  # Core sync logic
│   │   │   ├── __init__.py
│   │   │   ├── dms_sync.py            # DMS CDC task management
│   │   │   ├── dm_sync.py             # TiDB DM configuration + management
│   │   │   └── lag_monitor.py         # Replication lag tracking
│   │   │
│   │   ├── check/                 # Core check logic
│   │   │   ├── __init__.py
│   │   │   ├── table_checker.py       # Table existence comparison
│   │   │   ├── column_checker.py      # Column definition comparison
│   │   │   ├── row_checker.py         # Row-by-row data comparison
│   │   │   ├── count_checker.py       # Fast row count reconciliation
│   │   │   ├── checksum_checker.py    # Table/row checksum verification
│   │   │   └── continuous.py          # Continuous validation loop
│   │   │
│   │   └── rules/                 # Shared compatibility rules
│   │       ├── __init__.py
│   │       ├── tidb_compat.py         # All TiDB compatibility rules (source of truth)
│   │       ├── type_mapping.py        # Aurora → TiDB type mapping
│   │       └── collation_mapping.py   # Collation conversion map
│   │
│   ├── cli/                       # CLI-specific code (Click commands, Rich formatting)
│   │   ├── __init__.py
│   │   ├── scan_cmd.py            # `tishift scan` — calls core, formats with Rich
│   │   ├── convert_cmd.py         # `tishift convert` — calls core, writes files
│   │   ├── load_cmd.py            # `tishift load` — calls core, shows progress bars
│   │   ├── sync_cmd.py            # `tishift sync` — calls core, monitors
│   │   ├── check_cmd.py           # `tishift check` — calls core, displays results
│   │   └── formatters.py          # Rich tables, panels, progress bars for CLI output
│   │
│   └── mcp/                       # MCP-specific code (FastMCP tools, audit)
│       ├── __init__.py
│       ├── server.py              # FastMCP server, tool registration
│       ├── tools_read.py          # Read-only tools (scan_schema, assess, profile, etc.)
│       ├── tools_compute.py       # Compute tools (convert_schema, convert_sp, report)
│       ├── tools_write.py         # Write tools (apply_schema, load_table, start_sync)
│       └── audit.py               # JSONL audit log for every tool invocation
│
├── runbooks/                      # Migration runbook templates
│   ├── standard.md                # Standard Aurora → TiDB migration
│   ├── assessment-only.md         # Scan + report only (no migration)
│   ├── large-scale.md             # >1TB migrations with Lightning + CDC
│   └── partner-demo.md            # Quick demo flow for sales engineering
│
├── tests/
│   ├── conftest.py                # Shared fixtures (mock DB connections)
│   ├── test_core/                 # Core library tests (the important ones)
│   │   ├── test_scan/
│   │   ├── test_convert/
│   │   ├── test_load/
│   │   ├── test_sync/
│   │   └── test_check/
│   ├── test_cli/                  # CLI integration tests
│   ├── test_mcp/                  # MCP server tests (tool registration, audit)
│   └── fixtures/
│       ├── sample_aurora_schema.sql
│       ├── sample_stored_procedures.sql
│       └── expected_tidb_schema.sql
│
└── docs/
    ├── getting-started.md
    ├── cli-guide.md               # CLI usage documentation
    ├── mcp-guide.md               # MCP setup and usage documentation
    ├── runbook-guide.md           # How to write and customize runbooks
    ├── security-model.md          # Security boundaries, audit log, credentials
    ├── scan-guide.md
    ├── convert-guide.md
    ├── load-guide.md
    ├── sync-guide.md
    ├── check-guide.md
    └── partner-runbook.md         # Step-by-step for AWS partners
```

---

## Development Roadmap

### Phase 1: Core Library + Scanner MVP (Weeks 1-3)

Build the `core.scan` module as standalone library with CLI wrapper. This is the highest-value deliverable because it can be used by partners immediately for pre-sales assessment. **Critical: build as core library first, CLI wrapper second.** This enables MCP later without refactoring.

**Week 1:**
- Project scaffolding: pyproject.toml, core/ package structure, config loading, connection manager
- Core: schema inventory collector (all information_schema queries)
- Core: basic compatibility rule engine (blockers + warnings list)
- CLI wrapper: Click entry point calling core functions, Rich formatting

**Week 2:**
- Core: scoring engine (all 5 categories with weighted calculation)
- Core: data profile collector (table sizes, row counts, BLOB detection)
- Core: Aurora metadata collector (version, binlog format, server vars)
- CLI: Rich tables and progress bars

**Week 3:**
- Core: JSON report generator (primary output format, used by both CLI and MCP)
- Core: HTML report (Jinja2 template)
- Core: automation coverage calculator
- Core: basic query pattern collector (performance_schema)
- Unit tests for all core collectors and scoring

### Phase 2: Scanner AI + Cost (Weeks 4-5)

**Week 4:**
- Core: Claude API integration for stored procedure analysis
- Core: SP complexity local scoring (LOC, cursors, dynamic SQL)
- Core: AI difficulty rating + refactoring suggestions in report

**Week 5:**
- Core: CloudWatch cost collector (Aurora monthly cost estimation)
- Core: TiDB Cloud sizing recommendation engine
- Core: cost comparison section in report
- CLI: PDF executive summary
- End-to-end integration tests

### Phase 3: Convert + Check (Weeks 6-8)

**Week 6:**
- Core: `convert.schema_transformer` (all 10 conversion rules)
- Core: DDL output with before/after diff
- CLI: dry-run mode

**Week 7:**
- Core: SP → application code converter (Python template first)
- Core: AI-powered SP conversion
- Core: trigger → middleware converter

**Week 8:**
- Core: `check.table_checker` table structure comparison
- Core: row count reconciliation
- Core: row-level data comparison (batched, parallel)
- Core: JSON output with mismatch details

### Phase 4: Load + Sync (Weeks 9-12)

**Week 9:**
- Core: `load` with direct strategy (mysqldump → LOAD DATA)
- Core: strategy auto-selection based on data size
- Core: continuation token / resume support

**Week 10:**
- Core: DMS integration (boto3 automation for full load tasks)
- Core: TiDB Lightning integration

**Week 11:**
- Core: `sync` DMS CDC mode
- Core: TiDB DM config generation
- Core: lag monitoring

**Week 12:**
- Core: `check.continuous` mode
- Prometheus metrics for all tools
- Docker image
- PyInstaller binary builds
- CLI documentation
- Partner runbook (CLI version)

### Phase 5: MCP Server (Weeks 13-15)

This phase wraps the existing core library as an MCP server. Since all core logic already exists, this is purely interface work.

**Week 13:**
- FastMCP server scaffolding with tool registration
- Read-only tools: `scan_schema`, `assess_compatibility`, `profile_data`
- Read-only tools: `validate_table`, `validate_rows`, `check_sync_status`
- Audit log writer (JSONL)
- Unit tests for tool registration and parameter validation

**Week 14:**
- Compute tools: `convert_schema`, `convert_stored_procedure`, `generate_report`
- Write tools: `apply_schema`, `load_table`, `start_sync`
- Write tool safety: confirmation metadata, dry-run passthrough
- Security enforcement: source connections always read-only

**Week 15:**
- Migration runbook templates (standard, assessment-only, large-scale, partner-demo)
- MCP integration tests (mock Claude conversation → tool calls → verify results)
- `tishift-mcp` entry point in pyproject.toml
- MCP setup documentation
- Partner demo script + recording

---

## AWS Aurora Test Environment

For development and testing, you need an Aurora MySQL instance. Here are the options from cheapest to most realistic.

### Option 1: RDS MySQL (Cheapest — Free Tier)

If your AWS account qualifies for free tier: `db.t3.micro`, 750 hrs/month, 20 GB storage, free for 12 months.

```bash
aws rds create-db-instance \
  --db-instance-identifier tishift-test \
  --db-instance-class db.t3.micro \
  --engine mysql \
  --engine-version 8.0 \
  --master-username admin \
  --master-user-password 'YourSecurePassword123!' \
  --allocated-storage 20 \
  --publicly-accessible \
  --region us-east-1
```

Behaves identically to Aurora MySQL for migration testing.

### Option 2: Aurora Serverless v2 (~$43-50/month idle)

```bash
# Create parameter group with binlog_format=ROW (CRITICAL for CDC)
aws rds create-db-cluster-parameter-group \
  --db-cluster-parameter-group-name tishift-params \
  --db-parameter-group-family aurora-mysql8.0 \
  --description "TiShift test params"

aws rds modify-db-cluster-parameter-group \
  --db-cluster-parameter-group-name tishift-params \
  --parameters "ParameterName=binlog_format,ParameterValue=ROW,ApplyMethod=pending-reboot"

# Create cluster
aws rds create-db-cluster \
  --db-cluster-identifier tishift-test \
  --engine aurora-mysql \
  --engine-version 8.0.mysql_aurora.3.07.1 \
  --serverless-v2-scaling-configuration MinCapacity=0.5,MaxCapacity=4 \
  --master-username admin \
  --master-user-password 'YourSecurePassword123!' \
  --db-cluster-parameter-group-name tishift-params \
  --storage-encrypted

# Create instance
aws rds create-db-instance \
  --db-instance-identifier tishift-test-i1 \
  --db-cluster-identifier tishift-test \
  --engine aurora-mysql \
  --db-instance-class db.serverless

# Stop when not testing
aws rds stop-db-cluster --db-cluster-identifier tishift-test

# Delete when done
aws rds delete-db-instance --db-instance-identifier tishift-test-i1 --skip-final-snapshot
aws rds delete-db-cluster --db-cluster-identifier tishift-test --skip-final-snapshot
```

**IMPORTANT**: Aurora's default parameter group uses `binlog_format=MIXED` which CANNOT be modified. You MUST create a custom parameter group with `binlog_format=ROW` for CDC to work.

### Sample Test Data

```sql
CREATE DATABASE tishift_test;
USE tishift_test;

-- Standard tables (should migrate cleanly)
CREATE TABLE customers (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_email (email)
);

CREATE TABLE orders (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id BIGINT,
  total DECIMAL(10,2),
  status ENUM('pending','shipped','delivered'),
  metadata JSON,
  FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE audit_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  table_name VARCHAR(64),
  action VARCHAR(10),
  record_id BIGINT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stored procedure (scan should flag; convert should refactor)
DELIMITER //
CREATE PROCEDURE get_customer_orders(IN cust_id BIGINT)
BEGIN
  DECLARE total_orders INT;
  SELECT COUNT(*) INTO total_orders FROM orders WHERE customer_id = cust_id;
  SELECT c.name, c.email, total_orders as order_count,
         COALESCE(SUM(o.total), 0) as lifetime_value
  FROM customers c
  LEFT JOIN orders o ON c.id = o.customer_id
  WHERE c.id = cust_id
  GROUP BY c.id;
END //
DELIMITER ;

-- Trigger (scan should flag; convert should generate app middleware)
DELIMITER //
CREATE TRIGGER after_order_insert
AFTER INSERT ON orders
FOR EACH ROW
BEGIN
  INSERT INTO audit_log (table_name, action, record_id, created_at)
  VALUES ('orders', 'INSERT', NEW.id, NOW());
END //
DELIMITER ;

-- Sample data
INSERT INTO customers (name, email) VALUES
  ('Acme Corp', 'acme@example.com'),
  ('TechStart Inc', 'info@techstart.com'),
  ('DataFlow LLC', 'hello@dataflow.io');

INSERT INTO orders (customer_id, total, status, metadata) VALUES
  (1, 1500.00, 'delivered', '{"items": 3}'),
  (1, 750.50, 'shipped', '{"items": 1}'),
  (2, 3200.00, 'pending', '{"items": 5}');
```

---

## Positioning & Differentiation

**Why build this instead of telling customers to use existing tools?**

1. **No open-source tool targets Aurora → TiDB specifically.** Google has tools for Spanner, Yugabyte has tools for YugabyteDB, CockroachDB has tools for CockroachDB. TiDB has DM and Lightning but no pre-migration assessment tool.

2. **First database migration tool with an MCP interface.** Every competitor (MOLT, Voyager, Spanner Migration Tool) ships CLI-only. TiShift is the first migration toolkit that an AI can operate conversationally. Partners can demo a migration as a conversation, not a terminal session.

3. **Assessment is the hardest sell.** Partners can run `tishift scan` for free against a prospect's Aurora instance and hand them a professional report showing score, automation coverage, and cost savings. Via MCP, they can do this live in a meeting — "let me scan your database right now and show you."

4. **Stored procedures are the #1 blocker.** Every Aurora migration conversation stalls at "but we have 200 stored procedures." AI-powered conversion removes that objection.

5. **Data validation builds trust.** `tishift check` proves the migration worked. Without it, customers are nervous about cutover. Row-by-row proof eliminates that fear.

6. **Two interfaces, one engine.** CLI for production (deterministic, scriptable, auditable). MCP for exploration and demos (conversational, AI-guided). Partners choose what fits their workflow.

7. **Open source.** Apache 2.0 license. Partners can embed it, customize it, contribute to it. Builds ecosystem.

---

*Document version: 3.0*
*Prepared for PingCAP Partner Solutions Architecture Team*
*Ready for Claude Code daemon build execution*
