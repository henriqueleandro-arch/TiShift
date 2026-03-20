"""SQL Server licensing and TiDB Cloud cost estimator."""

from __future__ import annotations

from tishift_mssql.models import CostEstimate, SQLServerMetadata

# SQL Server licensing (2025 per-core pricing)
ENTERPRISE_PER_CORE_MONTHLY = 274.0
STANDARD_PER_CORE_MONTHLY = 99.0

# TiDB Cloud Starter pricing (as of March 2026)
STARTER_STORAGE_PER_GIB = 0.20  # $/GiB/month beyond free 25 GiB
STARTER_RU_PER_MILLION = 0.10   # $/1M RUs beyond free 250M/month
STARTER_FREE_STORAGE_GIB = 25.0
STARTER_FREE_RU_MILLIONS = 250.0

# TiDB Cloud Dedicated baseline (minimum 4 vCPU TiDB + TiKV)
DEDICATED_MIN_MONTHLY = 1376.0


def estimate_cost(
    metadata: SQLServerMetadata,
    tier: str = "starter",
    total_data_mb: float = 0.0,
) -> CostEstimate:
    """Estimate SQL Server licensing burn and TiDB Cloud target cost."""
    edition = (metadata.edition or "").lower()
    cores = max(metadata.cpu_count or 4, 4)

    if "enterprise" in edition:
        monthly_sql = cores * ENTERPRISE_PER_CORE_MONTHLY
        assumptions = ["Enterprise per-core licensing approximation", f"{cores} billable cores"]
    elif "standard" in edition:
        monthly_sql = cores * STANDARD_PER_CORE_MONTHLY
        assumptions = ["Standard per-core licensing approximation", f"{cores} billable cores"]
    else:
        monthly_sql = cores * STANDARD_PER_CORE_MONTHLY
        assumptions = ["Unknown edition; used standard baseline", f"{cores} billable cores"]

    # TiDB Cloud cost estimate
    total_gib = total_data_mb / 1024
    monthly_tidb = 0.0
    recommended = tier

    if tier == "starter":
        if total_gib <= STARTER_FREE_STORAGE_GIB:
            monthly_tidb = 0.0
            assumptions.append(f"TiDB Cloud Starter: {total_gib:.1f} GiB within {STARTER_FREE_STORAGE_GIB:.0f} GiB free tier")
        else:
            overage_gib = total_gib - STARTER_FREE_STORAGE_GIB
            monthly_tidb = overage_gib * STARTER_STORAGE_PER_GIB
            assumptions.append(f"TiDB Cloud Starter: {overage_gib:.1f} GiB overage × ${STARTER_STORAGE_PER_GIB}/GiB")
            recommended = "essential"
            assumptions.append("Recommend Essential tier for data exceeding Starter free limit")
    elif tier == "essential":
        # Rough estimate: storage + baseline compute
        monthly_tidb = max(total_gib * STARTER_STORAGE_PER_GIB, 20.0 * 30)  # ~$20/day minimum
        assumptions.append(f"TiDB Cloud Essential: estimated from storage ({total_gib:.1f} GiB) + baseline compute")
    elif tier == "dedicated":
        monthly_tidb = DEDICATED_MIN_MONTHLY
        assumptions.append(f"TiDB Cloud Dedicated: minimum ${DEDICATED_MIN_MONTHLY:.0f}/month (4 vCPU)")

    return CostEstimate(
        estimated_monthly_sqlserver_license_usd=round(monthly_sql, 2),
        estimated_monthly_tidb_cloud_usd=round(monthly_tidb, 2),
        recommended_tier=recommended,
        assumptions=assumptions,
    )
