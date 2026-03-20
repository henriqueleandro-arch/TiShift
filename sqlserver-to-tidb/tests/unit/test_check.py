from __future__ import annotations

from tishift_mssql.check.command import run_check
from tishift_mssql.config import TiShiftMSSQLConfig, SourceConfig


def _cfg() -> TiShiftMSSQLConfig:
    return TiShiftMSSQLConfig(source=SourceConfig(host="localhost", user="sa", password="x"))


def test_run_check_json_output(tmp_path) -> None:
    result = run_check(
        config=_cfg(),
        schema_only=False,
        tables="*",
        exclude_tables="",
        concurrency=4,
        row_batch_size=1000,
        sample_rate=1.0,
        continuous=False,
        interval=1,
        fail_on_mismatch=False,
        schema_mapping="flatten",
        output_formats=("json",),
        output_dir=tmp_path,
        console=None,
    )
    assert result.passed
    assert (tmp_path / "check-report.json").exists()
