"""Progress helpers for CLI execution."""

from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter

from rich.console import Console


@contextmanager
def step_progress(console: Console | None, label: str):
    """Print minimal step progress when console is available."""
    start = perf_counter()
    if console:
        console.print(f"[cyan]>[/cyan] {label}...")
    try:
        yield
    finally:
        if console:
            elapsed = perf_counter() - start
            console.print(f"[green]✓[/green] {label} ({elapsed:.1f}s)")
