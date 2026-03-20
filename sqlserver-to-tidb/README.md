# TiShift SQL Server

TiShift SQL Server is a Python toolkit for SQL Server to TiDB migration workflows.

## Commands

- `tishift-mssql scan`: Assess source readiness and generate reports.
- `tishift-mssql convert`: Convert scan output to TiDB DDL and code stubs.
- `tishift-mssql load`: Run initial bulk-load strategy orchestration.
- `tishift-mssql sync`: Start/stop/check CDC sync lifecycle.
- `tishift-mssql check`: Validate source/target consistency.

## Quick Start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

cp config/tishift-mssql.example.yaml tishift-mssql.yaml

# Scan
 tishift-mssql scan --config tishift-mssql.yaml --format cli --format json

# Convert from scan report
 tishift-mssql convert --scan-report ./tishift-reports/tishift-mssql-report.json --dry-run

# Load / Check / Sync
 tishift-mssql load --config tishift-mssql.yaml --strategy auto
 tishift-mssql check --config tishift-mssql.yaml --output cli,json
 tishift-mssql sync --config tishift-mssql.yaml --status
```

## Test

```bash
pytest tests -q
```
