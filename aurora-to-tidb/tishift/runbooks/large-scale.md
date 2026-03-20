# TiShift Runbook (Large Scale)

- Run: tishift scan --config tishift.yaml --include-query-log --ai
- If data > 1 TB: plan TiDB Lightning
- Use DMS/DM for CDC depending on environment
- Validate with tishift check --schema <database>
