"""Tests for load strategy selection."""

from __future__ import annotations

from tishift.core.load.strategy import select_strategy
from tishift.models import DataProfile, TargetDeployment


def test_select_strategy_direct():
    profile = DataProfile(total_data_mb=50 * 1024)
    plan = select_strategy(profile)
    assert plan.strategy == "direct"


def test_select_strategy_dms():
    profile = DataProfile(total_data_mb=200 * 1024)
    plan = select_strategy(profile)
    assert plan.strategy == "dms"


def test_select_strategy_cloud_import_default():
    """Default target is cloud — large datasets use cloud_import."""
    profile = DataProfile(total_data_mb=2000 * 1024)
    plan = select_strategy(profile)
    assert plan.strategy == "cloud_import"


def test_select_strategy_lightning_self_hosted():
    """Self-hosted target uses lightning for large datasets."""
    profile = DataProfile(total_data_mb=2000 * 1024)
    plan = select_strategy(profile, target=TargetDeployment.SELF_HOSTED)
    assert plan.strategy == "lightning"
