# TiShift Migration Runbook (Standard)

## Phase 1 — Scan
- Run: tishift scan --config tishift.yaml
- Review blockers, warnings, and automation coverage

## CHECKPOINT
- Approve to proceed to conversion

## Phase 2 — Convert
- Run: tishift convert --config tishift.yaml --scan-report ./tishift-reports/tishift-report.json
- Review conversion notes and diff

## CHECKPOINT
- Approve to apply schema

## Phase 3 — Apply
- Run: tishift convert --config tishift.yaml --scan-report ./tishift-reports/tishift-report.json --apply

## Phase 4 — Load
- Run: tishift load --config tishift.yaml --scan-report ./tishift-reports/tishift-report.json

## Phase 5 — Sync
- Run: tishift sync --config tishift.yaml

## Phase 6 — Check
- Run: tishift check --config tishift.yaml --schema <database>
