"""JSONL run logger for lessons-learned telemetry (Layer 1 — local only).

Every CLI invocation writes one JSONL file to ~/.tishift/runs/ with timestamped
events for each phase step.  All data is anonymized — no real table names, hosts,
or credentials leave the local log.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tishift import __version__
from tishift.models import ScanReport


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RUNS_DIR = Path.home() / ".tishift" / "runs"

_HOST_PATTERNS: list[tuple[str, list[str]]] = [
    ("localhost", ["localhost", "127.0.0.1", "::1"]),
    ("aws-aurora", [".cluster-", ".cluster-ro-"]),
    ("aws-rds", [".rds.amazonaws.com"]),
    ("tidb-cloud", [".tidbcloud.com", ".pingcap.com"]),
]


# ---------------------------------------------------------------------------
# Anonymization helpers
# ---------------------------------------------------------------------------

def anonymize_host(host: str) -> str:
    """Classify a hostname into a privacy-safe category."""
    lower = host.lower()
    for label, patterns in _HOST_PATTERNS:
        for pat in patterns:
            if lower == pat or pat in lower:
                return label
    return "other"


def fingerprint(name: str) -> str:
    """Return a 12-char hex fingerprint of *name* (sha256 prefix)."""
    return hashlib.sha256(name.encode()).hexdigest()[:12]


def summarize_report(report: ScanReport) -> dict[str, Any]:
    """Extract only numeric / categorical metrics from a ScanReport."""
    inv = report.schema_inventory
    dp = report.data_profile
    scoring = report.scoring
    assessment = report.assessment

    blocker_types = sorted({i.type for i in assessment.blockers})
    warning_types = sorted({i.type for i in assessment.warnings})

    summary: dict[str, Any] = {
        "source_type": anonymize_host(report.source_host),
        "database_fingerprint": fingerprint(report.database),
        "table_count": len(inv.tables),
        "column_count": len(inv.columns),
        "index_count": len(inv.indexes),
        "routine_count": len(inv.routines),
        "trigger_count": len(inv.triggers),
        "view_count": len(inv.views),
        "event_count": len(inv.events),
        "total_data_mb": round(dp.total_data_mb, 2),
        "total_rows": dp.total_rows,
        "blob_columns": len(dp.blob_columns),
        "blocker_count": len(assessment.blockers),
        "warning_count": len(assessment.warnings),
        "info_count": len(assessment.info),
        "blocker_types": blocker_types,
        "warning_types": warning_types,
        "overall_score": scoring.overall_score,
        "rating": scoring.rating.value,
    }

    if scoring.schema_compatibility:
        summary["schema_compat"] = scoring.schema_compatibility.score
    if scoring.data_complexity:
        summary["data_complexity"] = scoring.data_complexity.score
    if scoring.query_compatibility:
        summary["query_compat"] = scoring.query_compatibility.score
    if scoring.procedural_code:
        summary["procedural_code"] = scoring.procedural_code.score
    if scoring.operational_readiness:
        summary["operational"] = scoring.operational_readiness.score

    if report.automation:
        summary["automation_pct"] = round(
            report.automation.fully_automated_pct + report.automation.ai_assisted_pct,
            1,
        )

    return summary


# ---------------------------------------------------------------------------
# RunEvent dataclass
# ---------------------------------------------------------------------------

@dataclass
class RunEvent:
    """A single structured event in a run log."""

    run_id: str
    phase: str
    step: str
    outcome: str
    timestamp: str
    duration_ms: int | None
    metrics: dict[str, Any]
    error: str | None
    tishift_version: str


# ---------------------------------------------------------------------------
# RunLogger
# ---------------------------------------------------------------------------

class RunLogger:
    """Append-only JSONL logger for one CLI invocation phase.

    Creates ``~/.tishift/runs/`` on first write and writes one line per event.
    """

    def __init__(self, run_id: str | None = None, phase: str = "unknown") -> None:
        self.run_id = run_id or uuid.uuid4().hex
        self.phase = phase

        RUNS_DIR.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        filename = f"{ts}-{phase}-{self.run_id[:8]}.jsonl"
        self.path = RUNS_DIR / filename

    # -- core ---------------------------------------------------------------

    def log(
        self,
        step: str,
        outcome: str,
        metrics: dict[str, Any] | None = None,
        duration_ms: int | None = None,
        error: str | None = None,
    ) -> None:
        """Append one RunEvent as a JSON line."""
        event = RunEvent(
            run_id=self.run_id,
            phase=self.phase,
            step=step,
            outcome=outcome,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            duration_ms=duration_ms,
            metrics=metrics or {},
            error=error,
            tishift_version=__version__,
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event)) + "\n")

    # -- convenience --------------------------------------------------------

    def started(self, metrics: dict[str, Any] | None = None) -> None:
        """Log the start of this phase."""
        self.log("start", "started", metrics=metrics)

    def completed(self, metrics: dict[str, Any], duration_ms: int) -> None:
        """Log successful completion of this phase."""
        self.log("complete", "ok", metrics=metrics, duration_ms=duration_ms)

    def failed(self, error: Exception, duration_ms: int) -> None:
        """Log a phase failure with the exception info."""
        error_str = f"{type(error).__name__}: {error}"
        self.log("complete", "error", duration_ms=duration_ms, error=error_str)

    def step_ok(self, step: str, metrics: dict[str, Any], duration_ms: int) -> None:
        """Log a successful intermediate step."""
        self.log(step, "ok", metrics=metrics, duration_ms=duration_ms)
