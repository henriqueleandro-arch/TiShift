"""Direct load strategy (mysqldump + LOAD DATA)."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DirectLoadPlan:
    dump_command: str
    load_command: str


def build_direct_load_plan(
    *,
    source_host: str,
    source_port: int,
    source_user: str,
    target_host: str,
    target_port: int,
    target_user: str,
    database: str,
    output_dir: Path,
) -> DirectLoadPlan:
    output_dir.mkdir(parents=True, exist_ok=True)
    dump_file = output_dir / f"{database}.sql"

    # Use env vars for passwords to avoid exposing them in process listings
    # or generated scripts. All other values are shell-quoted to prevent injection.
    dump_command = (
        f"mysqldump -h {shlex.quote(source_host)} -P {shlex.quote(str(source_port))} "
        f"-u {shlex.quote(source_user)} "
        f"--single-transaction --routines --events "
        f"{shlex.quote(database)} > {shlex.quote(str(dump_file))}"
    )
    load_command = (
        f"mysql -h {shlex.quote(target_host)} -P {shlex.quote(str(target_port))} "
        f"-u {shlex.quote(target_user)} "
        f"{shlex.quote(database)} < {shlex.quote(str(dump_file))}"
    )
    return DirectLoadPlan(dump_command=dump_command, load_command=load_command)
