"""TiDB DM sync stubs."""

from __future__ import annotations

from tishift_mssql.sync.models import SyncStatus


def start_dm_sync(start_lsn: str | None) -> SyncStatus:
    """Start DM-based sync placeholder."""
    notes = ["DM sync started (placeholder)"]
    if start_lsn:
        notes.append(f"Start LSN: {start_lsn}")
    return SyncStatus(strategy="dm", running=True, lag_seconds=0, checkpoint=start_lsn, notes=notes)


def stop_dm_sync() -> SyncStatus:
    """Stop DM-based sync placeholder."""
    return SyncStatus(strategy="dm", running=False, lag_seconds=0, notes=["DM sync stopped (placeholder)"])
