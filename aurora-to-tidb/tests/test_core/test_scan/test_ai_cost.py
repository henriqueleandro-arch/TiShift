"""Tests for AI analyzer and cost analyzer."""

from __future__ import annotations

from tishift.config import AIConfig
from tishift.core.scan.analyzers.ai_analyzer import local_complexity_summary
from tishift.core.scan.analyzers.cost import analyze_costs
from tishift.models import CloudWatchMetrics, DataProfile


def test_ai_analyzer_disabled(sample_inventory):
    cfg = AIConfig(provider="none", api_key="")
    summary = local_complexity_summary(sample_inventory.routines)
    assert summary["routines"]


def test_cost_analyzer_basic(sample_data_profile, sample_aurora_metadata):
    metrics = CloudWatchMetrics(
        averages={
            "ServerlessDatabaseCapacity": 2.0,
            "VolumeBytesUsed": 100 * 1024 ** 3,
            "VolumeReadIOPs": 100.0,
            "VolumeWriteIOPs": 50.0,
        },
        maximums={},
    )

    # Force a smaller data profile for a predictable TiDB recommendation.
    profile = DataProfile(
        table_sizes=sample_data_profile.table_sizes,
        blob_columns=sample_data_profile.blob_columns,
        total_data_mb=20 * 1024,
        total_index_mb=0,
        total_rows=sample_data_profile.total_rows,
    )

    analysis = analyze_costs(metrics, profile, sample_aurora_metadata)
    assert analysis.aurora_monthly_estimate > 0
    assert analysis.tidb_monthly_estimate > 0
    assert analysis.tidb_recommendation.tier in ("Starter", "Essential", "Dedicated")
