from __future__ import annotations

import json

from tishift_mssql.config import SourceConfig, TiShiftMSSQLConfig
from tishift_mssql.load.command import run_load
from tishift_mssql.load.strategy import choose_strategy


def test_choose_strategy_auto_thresholds() -> None:
    # Dedicated tier preserves original behavior
    assert choose_strategy("auto", 10 * 1024, tier="dedicated") == "direct"
    assert choose_strategy("auto", 100 * 1024, tier="dedicated") == "dms"
    assert choose_strategy("auto", 600 * 1024, tier="dedicated") == "lightning"


def test_choose_strategy_starter_defaults_to_ticloud_import() -> None:
    assert choose_strategy("auto", 10 * 1024, tier="starter") == "ticloud_import"
    assert choose_strategy("auto", None, tier="starter") == "ticloud_import"


def test_choose_strategy_starter_rejects_lightning() -> None:
    import pytest
    with pytest.raises(ValueError, match="not available on TiDB Cloud Starter"):
        choose_strategy("lightning", 600 * 1024, tier="starter")


def test_choose_strategy_essential_rejects_lightning() -> None:
    import pytest
    with pytest.raises(ValueError, match="not available on TiDB Cloud Essential"):
        choose_strategy("lightning", 600 * 1024, tier="essential")


def test_run_load_uses_scan_report_for_auto_strategy(tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "tishift-mssql-report.json").write_text(
        json.dumps(
            {
                "data_profile": {"total_data_mb": 120 * 1024},
                "schema_inventory": {"tables": [{"schema_name": "dbo", "table_name": "users"}]},
            }
        )
    )
    cfg = TiShiftMSSQLConfig(
        source=SourceConfig(host="localhost", user="sa"),
        target={"tier": "dedicated"},
        output={"dir": str(reports_dir)},
    )
    result = run_load(
        config=cfg,
        strategy="auto",
        concurrency=2,
        tables="*",
        exclude_tables="",
        s3_bucket=None,
        dms_instance_class="dms.r5.large",
        resume=False,
        continuation_token=None,
        schema_first=True,
        drop_indexes=True,
        schema_mapping="flatten",
        output_dir=tmp_path / "load",
        console=None,
    )
    assert result.strategy == "dms"
    assert result.loaded_tables == ["dbo.users"]
