"""Cost comparison analyzer (Aurora vs TiDB Cloud)."""

from __future__ import annotations

import logging
from dataclasses import asdict

from tishift.models import (
    AuroraMetadata,
    CloudWatchMetrics,
    CostAnalysis,
    CostBreakdown,
    DataProfile,
    TiDBRecommendation,
)

logger = logging.getLogger(__name__)

_HOURS_PER_MONTH = 24 * 30

# Heuristic pricing constants (approximate, region-agnostic).
_AURORA_ACU_HOURLY_USD = 0.06
_AURORA_STORAGE_GB_MONTH_USD = 0.10
_AURORA_IO_MILLION_USD = 0.20

_TIDB_VCPU_HOURLY_USD = 0.08
_TIDB_STORAGE_GB_MONTH_USD = 0.10


def _get_metric(metrics: CloudWatchMetrics, name: str, default: float | None = None) -> float | None:
    if name in metrics.averages:
        return metrics.averages[name]
    if name in metrics.maximums:
        return metrics.maximums[name]
    return default


def _estimate_aurora_cost(metrics: CloudWatchMetrics) -> tuple[float, CostBreakdown, list[str]]:
    notes: list[str] = []

    avg_acu = _get_metric(metrics, "ServerlessDatabaseCapacity")
    storage_bytes = _get_metric(metrics, "VolumeBytesUsed") or 0.0
    storage_gb = storage_bytes / (1024 ** 3)

    read_iops = _get_metric(metrics, "VolumeReadIOPs") or 0.0
    write_iops = _get_metric(metrics, "VolumeWriteIOPs") or 0.0
    io_ops = (read_iops + write_iops) * 3600 * 24 * 30
    io_ops_million = io_ops / 1_000_000

    if avg_acu is None:
        notes.append("ServerlessDatabaseCapacity not available; compute cost set to 0")
        compute_cost = 0.0
    else:
        compute_cost = avg_acu * _AURORA_ACU_HOURLY_USD * _HOURS_PER_MONTH

    storage_cost = storage_gb * _AURORA_STORAGE_GB_MONTH_USD
    io_cost = io_ops_million * _AURORA_IO_MILLION_USD

    total = compute_cost + storage_cost + io_cost
    breakdown = CostBreakdown(
        compute=round(compute_cost, 2),
        storage=round(storage_cost, 2),
        io=round(io_cost, 2),
    )
    return round(total, 2), breakdown, notes


def _recommend_tidb(profile: DataProfile, metadata: AuroraMetadata) -> TiDBRecommendation:
    total_gb = profile.total_data_mb / 1024

    if total_gb <= 50:
        tier = "Starter"
        nodes = 1
        vcpu = 2
        ram_gb = 8
    elif total_gb <= 500:
        tier = "Essential"
        nodes = 2
        vcpu = 4
        ram_gb = 16
    else:
        tier = "Dedicated"
        nodes = 3
        vcpu = 8
        ram_gb = 32

    storage_gb = max(int(total_gb * 2), 50 if tier == "Starter" else 100)
    monthly_compute = nodes * vcpu * _TIDB_VCPU_HOURLY_USD * _HOURS_PER_MONTH
    monthly_storage = storage_gb * _TIDB_STORAGE_GB_MONTH_USD
    monthly_total = monthly_compute + monthly_storage

    return TiDBRecommendation(
        tier=tier,
        nodes=nodes,
        vcpu=vcpu,
        ram_gb=ram_gb,
        storage_gb=storage_gb,
        monthly_estimate=round(monthly_total, 2),
    )


def analyze_costs(
    metrics: CloudWatchMetrics,
    profile: DataProfile,
    metadata: AuroraMetadata,
) -> CostAnalysis:
    """Estimate Aurora monthly cost and TiDB Cloud recommendation."""
    aurora_total, breakdown, notes = _estimate_aurora_cost(metrics)
    tidb_rec = _recommend_tidb(profile, metadata)

    savings_pct = 0.0
    if aurora_total > 0:
        savings_pct = round((aurora_total - tidb_rec.monthly_estimate) / aurora_total * 100, 1)

    analysis = CostAnalysis(
        aurora_monthly_estimate=aurora_total,
        tidb_monthly_estimate=tidb_rec.monthly_estimate,
        savings_pct=savings_pct,
        aurora_breakdown=breakdown,
        tidb_recommendation=tidb_rec,
        notes=notes,
    )

    logger.info("Cost analysis: aurora=%.2f, tidb=%.2f", aurora_total, tidb_rec.monthly_estimate)
    return analysis


def summarize_costs(costs: CostAnalysis) -> dict[str, float | str]:
    return {
        "aurora_monthly_estimate": costs.aurora_monthly_estimate,
        "tidb_monthly_estimate": costs.tidb_monthly_estimate,
        "savings_pct": costs.savings_pct,
        "tier": costs.tidb_recommendation.tier,
    }
