"""CloudWatch metrics collector for Aurora cost estimation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from tishift.config import AWSConfig
from tishift.models import CloudWatchMetrics

logger = logging.getLogger(__name__)

_METRICS = [
    "CPUUtilization",
    "DatabaseConnections",
    "FreeableMemory",
    "ReadIOPS",
    "WriteIOPS",
    "ReadLatency",
    "WriteLatency",
    "VolumeBytesUsed",
    "VolumeReadIOPs",
    "VolumeWriteIOPs",
    "ServerlessDatabaseCapacity",
]


def _infer_identifier(source_host: str) -> str | None:
    if not source_host:
        return None
    return source_host.split(".")[0] if "." in source_host else source_host


def collect_cloudwatch_metrics(
    *,
    aws: AWSConfig,
    source_host: str,
) -> CloudWatchMetrics | None:
    """Collect CloudWatch metrics for the Aurora instance/cluster.

    Returns None if boto3 is unavailable or metrics cannot be fetched.
    """
    try:
        import boto3  # type: ignore
    except ImportError:
        logger.warning("boto3 not installed; install tishift[aws] for cost analysis")
        return None

    identifier = aws.db_cluster_identifier or aws.db_instance_identifier or _infer_identifier(source_host)
    if not identifier:
        logger.warning("No DB identifier available for CloudWatch metrics")
        return None

    dimension_name = "DBClusterIdentifier" if aws.db_cluster_identifier else "DBInstanceIdentifier"

    session_kwargs: dict[str, Any] = {}
    if aws.profile:
        session_kwargs["profile_name"] = aws.profile
    session = boto3.Session(**session_kwargs)
    client = session.client("cloudwatch", region_name=aws.region)

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)

    queries = []
    for idx, metric_name in enumerate(_METRICS):
        queries.append({
            "Id": f"m{idx}",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/RDS",
                    "MetricName": metric_name,
                    "Dimensions": [
                        {"Name": dimension_name, "Value": identifier}
                    ],
                },
                "Period": 3600,
                "Stat": "Average",
            },
            "ReturnData": True,
        })
        queries.append({
            "Id": f"x{idx}",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/RDS",
                    "MetricName": metric_name,
                    "Dimensions": [
                        {"Name": dimension_name, "Value": identifier}
                    ],
                },
                "Period": 3600,
                "Stat": "Maximum",
            },
            "ReturnData": True,
        })

    try:
        response = client.get_metric_data(
            MetricDataQueries=queries,
            StartTime=start_time,
            EndTime=end_time,
            ScanBy="TimestampAscending",
        )
    except Exception as exc:  # pragma: no cover - network errors
        logger.warning("CloudWatch metrics fetch failed: %s", exc)
        return None

    averages: dict[str, float] = {}
    maximums: dict[str, float] = {}

    for result in response.get("MetricDataResults", []):
        metric_id = result.get("Id")
        if not metric_id:
            continue
        values = result.get("Values", [])
        if not values:
            continue
        # We queried Average and Maximum separately.
        idx = int(metric_id[1:])
        metric_name = _METRICS[idx]
        avg_value = sum(values) / len(values)
        if metric_id.startswith("m"):
            averages[metric_name] = avg_value
        else:
            maximums[metric_name] = max(values)

    if not averages and not maximums:
        return None

    metrics = CloudWatchMetrics(averages=averages, maximums=maximums)
    logger.info("CloudWatch metrics collected for %s", identifier)
    return metrics
