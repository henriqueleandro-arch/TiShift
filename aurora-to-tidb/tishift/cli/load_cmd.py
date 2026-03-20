"""CLI command: tishift load."""

from __future__ import annotations

import json
import time
from pathlib import Path

import click

from tishift.config import load_config
from tishift.core.load.cloud_import_loader import build_cloud_import_plan
from tishift.core.load.direct_loader import build_direct_load_plan
from tishift.core.load.dms_loader import build_dms_plan
from tishift.core.load.lightning_loader import build_lightning_plan
from tishift.core.load.strategy import select_strategy
from tishift.models import DataProfile, TargetDeployment
from tishift.run_logger import RunLogger


@click.command("load")
@click.option(
    "--config", "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=Path("tishift.yaml"),
    help="Path to config file.",
)
@click.option(
    "--scan-report",
    "scan_report_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to JSON report from tishift scan.",
)
@click.option(
    "--target",
    type=click.Choice(["cloud", "self-hosted"]),
    default="cloud",
    help="Target deployment: cloud (TiDB Cloud) or self-hosted.",
)
@click.option("--strategy", default=None, help="Force strategy: direct, dms, lightning, cloud_import.")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("./tishift-load"),
    help="Where to write load plan scripts.",
)
def load_command(
    config_path: Path,
    scan_report_path: Path,
    target: str,
    strategy: str | None,
    output_dir: Path,
) -> None:
    """Generate load plan for initial data transfer."""
    cfg = load_config(config_path)
    data = json.loads(scan_report_path.read_text())
    profile = _profile_from_report(data)
    target_enum = TargetDeployment(target)

    logger = RunLogger(phase="load")
    logger.started(metrics={"total_data_mb": round(profile.total_data_mb, 2), "target": target})
    t0 = time.monotonic()

    try:
        if strategy is None:
            plan = select_strategy(profile, target=target_enum)
            strategy = plan.strategy

        output_dir.mkdir(parents=True, exist_ok=True)

        if strategy == "direct":
            direct = build_direct_load_plan(
                source_host=cfg.source.host,
                source_port=cfg.source.port,
                source_user=cfg.source.user,
                target_host=cfg.target.host,
                target_port=cfg.target.port,
                target_user=cfg.target.user,
                database=cfg.source.database if cfg.source.database != "*" else "",
                output_dir=output_dir,
            )
            script = (
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "# Set SOURCE_PASSWORD and TARGET_PASSWORD as environment variables before running.\n"
                "# Do NOT pass passwords on the command line — they are visible in process listings.\n"
                "export MYSQL_PWD=\"$SOURCE_PASSWORD\"\n"
                f"{direct.dump_command}\n"
                "export MYSQL_PWD=\"$TARGET_PASSWORD\"\n"
                f"{direct.load_command}\n"
                "unset MYSQL_PWD\n"
            )
            (output_dir / "direct-load.sh").write_text(script)
        elif strategy == "dms":
            plan = build_dms_plan("tishift-load-task")
            (output_dir / "dms-plan.txt").write_text(plan.notes)
        elif strategy == "cloud_import":
            plan = build_cloud_import_plan()
            (output_dir / "cloud-import-plan.txt").write_text(plan.notes)
        elif strategy == "lightning":
            plan = build_lightning_plan()
            (output_dir / "lightning-plan.txt").write_text(plan.notes)
        else:
            raise click.ClickException(f"Unknown strategy: {strategy}")
    except Exception as exc:
        logger.failed(exc, duration_ms=int((time.monotonic() - t0) * 1000))
        raise

    logger.completed(
        metrics={
            "strategy": strategy,
            "total_data_mb": round(profile.total_data_mb, 2),
        },
        duration_ms=int((time.monotonic() - t0) * 1000),
    )


def _profile_from_report(data: dict) -> DataProfile:
    profile = data.get("data_profile") or {}
    total_gb = profile.get("total_data_size_gb", 0)
    return DataProfile(total_data_mb=total_gb * 1024)
