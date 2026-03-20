"""Strategy selection for bulk load."""

from __future__ import annotations


def choose_strategy(strategy: str, total_data_mb: float | None, tier: str = "starter") -> str:
    """Select load strategy based on explicit choice, profile size, and target tier.

    Starter only supports direct load and ticloud CLI import.
    Essential supports direct and DMS. Dedicated supports all strategies.
    """
    normalized = strategy.lower()

    if tier == "starter":
        if normalized in ("dms", "lightning"):
            raise ValueError(
                f"Strategy '{normalized}' is not available on TiDB Cloud Starter. "
                "Use 'ticloud_import' or 'direct' instead."
            )
        if normalized == "auto":
            return "ticloud_import"
        return normalized

    if tier == "essential":
        if normalized == "lightning":
            raise ValueError(
                "TiDB Lightning is not available on TiDB Cloud Essential. "
                "Use 'dms' or 'direct' instead, or upgrade to Dedicated."
            )
        if normalized != "auto":
            return normalized
        if total_data_mb is None or total_data_mb < 50 * 1024:
            return "direct"
        return "dms"

    # Dedicated / self-hosted: original logic
    if normalized != "auto":
        return normalized
    if total_data_mb is None or total_data_mb < 50 * 1024:
        return "direct"
    if total_data_mb <= 500 * 1024:
        return "dms"
    return "lightning"
