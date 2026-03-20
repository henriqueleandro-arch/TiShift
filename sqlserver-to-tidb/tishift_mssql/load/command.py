"""Load command orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from tishift_mssql.config import TiShiftMSSQLConfig
from tishift_mssql.load.continuation import issue_token, read_state, write_state
from tishift_mssql.load.direct_loader import run_direct_load
from tishift_mssql.load.dms_loader import run_dms_load
from tishift_mssql.load.lightning_loader import run_lightning_load
from tishift_mssql.load.models import LoadPlan, LoadResult
from tishift_mssql.load.strategy import choose_strategy


def _parse_list(csv_value: str) -> list[str]:
    if csv_value.strip() == "*":
        return []
    return [item.strip() for item in csv_value.split(",") if item.strip()]


def _load_latest_scan_report(config: TiShiftMSSQLConfig) -> dict[str, object] | None:
    path = Path(config.output.dir) / "tishift-mssql-report.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    return payload if isinstance(payload, dict) else None


def _infer_total_data_mb(scan_report: dict[str, object] | None) -> float | None:
    if not scan_report:
        return None
    data_profile = scan_report.get("data_profile")
    if not isinstance(data_profile, dict):
        return None
    total = data_profile.get("total_data_mb")
    if isinstance(total, (int, float)):
        return float(total)
    return None


def _discover_tables(scan_report: dict[str, object] | None) -> list[str]:
    if not scan_report:
        return ["*"]
    inventory = scan_report.get("schema_inventory")
    if not isinstance(inventory, dict):
        return ["*"]
    tables = inventory.get("tables")
    if not isinstance(tables, list):
        return ["*"]
    discovered: list[str] = []
    for table in tables:
        if not isinstance(table, dict):
            continue
        schema = str(table.get("schema_name") or "dbo")
        name = str(table.get("table_name") or "")
        if not name:
            continue
        discovered.append(f"{schema}.{name}")
    return discovered or ["*"]


def run_load(
    *,
    config: TiShiftMSSQLConfig,
    strategy: str,
    concurrency: int,
    tables: str,
    exclude_tables: str,
    s3_bucket: str | None,
    dms_instance_class: str,
    resume: bool,
    continuation_token: str | None,
    schema_first: bool,
    drop_indexes: bool,
    schema_mapping: str,
    output_dir: Path,
    console: Console | None,
) -> LoadResult:
    """Run data load strategy selection and execution."""
    _ = config
    output_dir.mkdir(parents=True, exist_ok=True)

    if resume:
        if not continuation_token:
            raise ValueError("--resume requires --continuation-token")
        payload = read_state(output_dir, continuation_token)
        prior_loaded = payload.get("loaded_tables")
        if isinstance(prior_loaded, list):
            if console:
                console.print(f"Resuming token {continuation_token}: {len(prior_loaded)} tables already loaded")

    selected_tables = _parse_list(tables)
    excluded = _parse_list(exclude_tables)
    scan_report = _load_latest_scan_report(config)
    if not selected_tables:
        selected_tables = _discover_tables(scan_report)

    inferred_size_mb = _infer_total_data_mb(scan_report)
    tier = config.target.tier if config else "starter"
    chosen = choose_strategy(strategy, inferred_size_mb, tier=tier)
    plan = LoadPlan(
        strategy=chosen,
        tables=selected_tables,
        excluded_tables=excluded,
        concurrency=max(1, concurrency),
        schema_first=schema_first,
        drop_indexes=drop_indexes,
        schema_mapping=schema_mapping,
    )

    if chosen == "direct":
        result = run_direct_load(plan)
    elif chosen == "dms":
        result = run_dms_load(plan, dms_instance_class)
    elif chosen == "lightning":
        result = run_lightning_load(plan, s3_bucket)
    elif chosen == "ticloud_import":
        from tishift_mssql.load.ticloud_loader import run_ticloud_import
        cloud_cfg = config.cloud if config else None
        result = run_ticloud_import(
            plan,
            cluster_id=cloud_cfg.cluster_id if cloud_cfg else "",
            project_id=cloud_cfg.project_id if cloud_cfg else "",
        )
    else:
        raise ValueError(f"Unsupported strategy: {chosen}")

    token = issue_token()
    result.continuation_token = token

    payload = {
        "strategy": result.strategy,
        "total_tables": result.total_tables,
        "loaded_tables": result.loaded_tables,
        "skipped_tables": result.skipped_tables,
        "notes": result.notes,
    }
    write_state(output_dir, token, payload)

    summary_path = output_dir / "load-summary.json"
    summary_path.write_text(json.dumps(payload | {"continuation_token": token}, indent=2) + "\n")

    if console:
        console.print(f"Load strategy: {result.strategy}")
        console.print(f"Loaded tables: {len(result.loaded_tables)} / {result.total_tables}")
        console.print(f"Continuation token: {token}")

    return result
