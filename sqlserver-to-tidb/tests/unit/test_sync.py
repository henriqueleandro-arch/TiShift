from __future__ import annotations

from tishift_mssql.sync.command import run_sync
from tishift_mssql.config import TiShiftMSSQLConfig, SourceConfig


def _cfg() -> TiShiftMSSQLConfig:
    return TiShiftMSSQLConfig(source=SourceConfig(host="localhost", user="sa", password="x"))


def test_run_sync_start_status_stop(tmp_path) -> None:
    started = run_sync(
        config=_cfg(),
        strategy="dms",
        start_lsn="0000001",
        dms_task_arn=None,
        status_only=False,
        stop=False,
        output_dir=tmp_path,
        console=None,
    )
    assert started.running

    status = run_sync(
        config=_cfg(),
        strategy="dms",
        start_lsn=None,
        dms_task_arn=None,
        status_only=True,
        stop=False,
        output_dir=tmp_path,
        console=None,
    )
    assert status.running

    stopped = run_sync(
        config=_cfg(),
        strategy="dms",
        start_lsn=None,
        dms_task_arn=None,
        status_only=False,
        stop=True,
        output_dir=tmp_path,
        console=None,
    )
    assert not stopped.running
