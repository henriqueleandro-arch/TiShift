"""DMS CDC sync stubs."""

from __future__ import annotations

from tishift_mssql.sync.models import SyncStatus


def start_dms_sync(start_lsn: str | None, dms_task_arn: str | None) -> SyncStatus:
    """Start DMS-based CDC sync placeholder."""
    notes = ["DMS CDC sync started (placeholder)"]
    if dms_task_arn:
        notes.append(f"Task ARN: {dms_task_arn}")
    if start_lsn:
        notes.append(f"Start LSN: {start_lsn}")
    return SyncStatus(strategy="dms", running=True, lag_seconds=0, checkpoint=start_lsn, notes=notes)


def stop_dms_sync(dms_task_arn: str | None) -> SyncStatus:
    """Stop DMS-based CDC sync placeholder."""
    notes = ["DMS CDC sync stopped (placeholder)"]
    if dms_task_arn:
        notes.append(f"Task ARN: {dms_task_arn}")
    return SyncStatus(strategy="dms", running=False, lag_seconds=0, notes=notes)
