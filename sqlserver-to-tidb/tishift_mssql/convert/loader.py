"""Loaders for conversion input artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_scan_report(path: Path) -> dict[str, Any]:
    """Load scan report JSON for conversion."""
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("Scan report must be a JSON object")
    if "schema_inventory" not in payload:
        raise ValueError("Scan report missing 'schema_inventory'")
    return payload
