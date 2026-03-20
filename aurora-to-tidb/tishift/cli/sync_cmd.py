"""CLI command: tishift sync."""

from __future__ import annotations

from pathlib import Path

import click

from tishift.config import load_config
from tishift.core.sync.dm_sync import build_dm_plan
from tishift.core.sync.dms_sync import build_dms_sync_plan


@click.command("sync")
@click.option(
    "--config", "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=Path("tishift.yaml"),
    help="Path to config file.",
)
@click.option("--strategy", default="dms", help="CDC strategy: dms or dm.")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("./tishift-sync"),
    help="Where to write sync plan files.",
)
def sync_command(config_path: Path, strategy: str, output_dir: Path) -> None:
    """Generate CDC sync plan."""
    load_config(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    if strategy == "dms":
        plan = build_dms_sync_plan()
        (output_dir / "dms-sync-plan.txt").write_text(plan.notes)
    elif strategy == "dm":
        plan = build_dm_plan()
        (output_dir / "dm-sync-plan.txt").write_text(plan.notes)
    else:
        raise click.ClickException(f"Unknown strategy: {strategy}")
