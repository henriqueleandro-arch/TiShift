# TiShift (Aurora MySQL -> TiDB)

TiShift is a migration toolkit with a core library and CLI for assessing, converting, and migrating Aurora MySQL to TiDB.

## Quick Start

```bash
# Scan
python -m tishift.cli scan --config tishift.yaml

# Convert
python -m tishift.cli convert --config tishift.yaml --scan-report ./tishift-reports/tishift-report.json

# Load (plan)
python -m tishift.cli load --config tishift.yaml --scan-report ./tishift-reports/tishift-report.json

# Sync (plan)
python -m tishift.cli sync --config tishift.yaml

# Check
python -m tishift.cli check --config tishift.yaml --schema mydb
```

## Features

- Scan: readiness scoring, compatibility checks, AI SP analysis, cost estimation
- Convert: schema DDL conversion + SP/trigger/event skeletons
- Load: strategy selection (direct/DMS/Lightning)
- Sync: CDC plan generation (DMS/DM)
- Check: row count and structure validation
- MCP: conversational interface via `tishift-mcp`

## Config

See `aurora-to-tidb-migration-plan.md` for full specification and `tishift.yaml` schema.
