"""Continuous check runner."""

from __future__ import annotations

import time
from collections.abc import Callable

from tishift_mssql.check.models import CheckResult


def run_continuous(check_fn: Callable[[], CheckResult], interval: int, iterations: int = 2) -> list[CheckResult]:
    """Run periodic checks (bounded iterations for MVP safety)."""
    results: list[CheckResult] = []
    for _ in range(max(1, iterations)):
        results.append(check_fn())
        time.sleep(max(1, interval))
    return results
