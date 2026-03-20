"""Load strategy selection."""

from __future__ import annotations

from dataclasses import dataclass

from tishift.models import DataProfile, TargetDeployment


@dataclass(frozen=True)
class LoadPlan:
    strategy: str
    reason: str


def select_strategy(
    profile: DataProfile,
    target: TargetDeployment = TargetDeployment.CLOUD,
) -> LoadPlan:
    total_gb = profile.total_data_mb / 1024
    if total_gb < 100:
        return LoadPlan(strategy="direct", reason="< 100 GB")
    if total_gb < 1024:
        return LoadPlan(strategy="dms", reason="100 GB - 1 TB")
    if target == TargetDeployment.CLOUD:
        return LoadPlan(strategy="cloud_import", reason=">= 1 TB on TiDB Cloud")
    return LoadPlan(strategy="lightning", reason=">= 1 TB (self-hosted)")
