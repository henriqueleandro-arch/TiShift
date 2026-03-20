"""JSON report writer."""

from __future__ import annotations

import json
from pathlib import Path

from tishift_mssql.models import ScanReport, to_dict


def generate_json_report(report: ScanReport, path: Path) -> None:
    """Serialize report to JSON file path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_dict(report), indent=2, sort_keys=True))
