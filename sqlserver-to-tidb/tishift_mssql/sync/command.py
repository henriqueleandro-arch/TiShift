"""Sync command orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from tishift_mssql.config import TiShiftMSSQLConfig
from tishift_mssql.sync.dm_sync import start_dm_sync, stop_dm_sync
from tishift_mssql.sync.dms_sync import start_dms_sync, stop_dms_sync
from tishift_mssql.sync.lag_monitor import current_lag_seconds
from tishift_mssql.sync.models import SyncStatus


STATE_FILE = "sync-status.json"


def _status_path(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / STATE_FILE


def _save_status(output_dir: Path, status: SyncStatus) -> None:
    payload = {
        "strategy": status.strategy,
        "running": status.running,
        "lag_seconds": status.lag_seconds,
        "checkpoint": status.checkpoint,
        "notes": status.notes,
    }
    _status_path(output_dir).write_text(json.dumps(payload, indent=2) + "\n")


def _load_status(output_dir: Path) -> SyncStatus | None:
    path = _status_path(output_dir)
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        return None
    return SyncStatus(
        strategy=str(payload.get("strategy") or "dms"),
        running=bool(payload.get("running")),
        lag_seconds=int(payload.get("lag_seconds") or 0),
        checkpoint=(str(payload["checkpoint"]) if payload.get("checkpoint") else None),
        notes=[str(n) for n in payload.get("notes", []) if isinstance(n, str)],
    )


def run_sync(
    *,
    config: TiShiftMSSQLConfig,
    strategy: str,
    start_lsn: str | None,
    dms_task_arn: str | None,
    status_only: bool,
    stop: bool,
    output_dir: Path,
    console: Console | None,
) -> SyncStatus:
    """Control CDC sync lifecycle."""
    _ = config
    chosen = strategy.lower()

    if status_only:
        stored = _load_status(output_dir)
        if stored is None:
            stored = SyncStatus(strategy=chosen, running=False, lag_seconds=0, notes=["No sync state found"])
        stored.lag_seconds = current_lag_seconds() if stored.running else 0
        _save_status(output_dir, stored)
        if console:
            console.print(f"Strategy: {stored.strategy}")
            console.print(f"Running: {stored.running}")
            console.print(f"Lag (s): {stored.lag_seconds}")
        return stored

    if stop:
        if chosen == "dms":
            status = stop_dms_sync(dms_task_arn)
        elif chosen == "dm":
            status = stop_dm_sync()
        else:
            raise ValueError(f"Unsupported sync strategy: {chosen}")
    else:
        if chosen == "dms":
            status = start_dms_sync(start_lsn, dms_task_arn)
        elif chosen == "dm":
            status = start_dm_sync(start_lsn)
        else:
            raise ValueError(f"Unsupported sync strategy: {chosen}")

    status.lag_seconds = current_lag_seconds() if status.running else 0
    _save_status(output_dir, status)

    if console:
        console.print(f"Strategy: {status.strategy}")
        console.print(f"Running: {status.running}")
        console.print(f"Lag (s): {status.lag_seconds}")
    return status
