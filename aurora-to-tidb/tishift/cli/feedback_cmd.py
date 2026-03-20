"""CLI command: tishift feedback.

Browse and export anonymized run logs from ~/.tishift/runs/.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from tishift.run_logger import RUNS_DIR


@click.command("feedback")
@click.option("--export", "do_export", is_flag=True, help="Pretty-print the latest run log as JSON.")
@click.option("--list", "do_list", is_flag=True, help="List all run logs with date, phase, outcome, score.")
def feedback_command(do_export: bool, do_list: bool) -> None:
    """Browse and export anonymized run logs."""
    if not RUNS_DIR.exists():
        raise click.ClickException(f"No run logs found. Directory does not exist: {RUNS_DIR}")

    log_files = sorted(RUNS_DIR.glob("*.jsonl"))
    if not log_files:
        raise click.ClickException("No run logs found in ~/.tishift/runs/")

    if do_list:
        _list_runs(log_files)
    elif do_export:
        _export_latest(log_files)
    else:
        click.echo("Use --list to browse runs or --export to print the latest log.")


def _list_runs(log_files: list[Path]) -> None:
    """Print a table of all run logs."""
    click.echo(f"{'Date':<22} {'Phase':<10} {'Outcome':<10} {'Score':<6} {'File'}")
    click.echo("-" * 80)

    for path in log_files:
        events = _read_events(path)
        if not events:
            continue

        first = events[0]
        last = events[-1]

        date = first.get("timestamp", "?")[:19]
        phase = first.get("phase", "?")
        outcome = last.get("outcome", "?")
        score = last.get("metrics", {}).get("overall_score")
        if score is None:
            score = last.get("metrics", {}).get("score")
        score_str = str(score) if score is not None else "-"

        click.echo(f"{date:<22} {phase:<10} {outcome:<10} {score_str:<6} {path.name}")


def _export_latest(log_files: list[Path]) -> None:
    """Pretty-print the latest run log as JSON array."""
    latest = log_files[-1]
    events = _read_events(latest)
    click.echo(json.dumps(events, indent=2))


def _read_events(path: Path) -> list[dict]:
    """Read all events from a JSONL file."""
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events
