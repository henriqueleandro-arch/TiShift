"""JSON report generator.

Serializes a ScanReport into the spec-defined JSON structure.
This is the primary interchange format used by the CLI.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from tishift.models import ScanReport


def _serialize(obj: Any) -> Any:
    """Custom serializer for dataclass fields."""
    if isinstance(obj, datetime):
        return obj.isoformat() + "Z"
    if hasattr(obj, "value"):  # Enum
        return obj.value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def generate_json_report(report: ScanReport) -> dict[str, Any]:
    """Convert a ScanReport to the spec-defined JSON structure."""
    total_gb = report.data_profile.total_data_mb / 1024
    total_index_gb = report.data_profile.total_index_mb / 1024

    # Estimate data transfer time at ~100 Mbps.
    transfer_hours = round(total_gb * 1024 / (100 / 8 * 3600) * 1000, 1) if total_gb else 0

    output: dict[str, Any] = {
        "version": report.version,
        "generated_at": report.generated_at.isoformat() + "Z",
        "source": {
            "host": report.source_host,
            "aurora_version": report.aurora_metadata.aurora_version or "N/A",
            "mysql_version": report.aurora_metadata.mysql_version or "N/A",
            "binlog_format": report.aurora_metadata.binlog_format or "N/A",
            "character_set": report.aurora_metadata.character_set_server or "N/A",
            "collation": report.aurora_metadata.collation_server or "N/A",
        },
        "summary": {
            "overall_score": report.scoring.overall_score,
            "rating": report.scoring.rating.value,
            "database_count": len(
                {t.table_schema for t in report.schema_inventory.tables}
            ),
            "table_count": len(report.schema_inventory.tables),
            "total_data_size_gb": round(total_gb, 1),
            "total_index_size_gb": round(total_index_gb, 1),
            "estimated_data_transfer_hours": transfer_hours,
            "automation_coverage_pct": report.automation.fully_automated_pct,
            "ai_assisted_pct": report.automation.ai_assisted_pct,
            "manual_required_pct": report.automation.manual_required_pct,
        },
        "scores": {},
        "issues": {
            "blockers": [],
            "warnings": [],
            "info": [],
        },
        "schema_details": {
            "tables": [],
            "stored_procedures": [],
            "triggers": [],
            "views": [],
            "foreign_keys": [],
            "indexes": [],
        },
        "schema_inventory": {
            "tables": [],
            "columns": [],
            "indexes": [],
            "foreign_keys": [],
            "routines": [],
            "triggers": [],
            "views": [],
            "events": [],
            "partitions": [],
            "charset_usage": [],
        },
        "data_profile": {
            "largest_tables": [],
            "blob_columns": [],
            "total_row_count": report.data_profile.total_rows,
        },
        "sp_analysis": [],
        "cost_analysis": None,
    }

    # Scores
    for cat in [
        report.scoring.schema_compatibility,
        report.scoring.data_complexity,
        report.scoring.query_compatibility,
        report.scoring.procedural_code,
        report.scoring.operational_readiness,
    ]:
        if cat is not None:
            output["scores"][cat.name] = {
                "score": cat.score,
                "max": cat.max_score,
                "deductions": cat.deductions,
            }

    # Issues
    for issue in report.assessment.blockers:
        output["issues"]["blockers"].append({
            "type": issue.type,
            "object": issue.object_name,
            "severity": issue.severity.value,
            "message": issue.message,
            "suggestion": issue.suggestion,
        })
    for issue in report.assessment.warnings:
        entry: dict[str, Any] = {
            "type": issue.type,
            "object": issue.object_name,
            "severity": issue.severity.value,
            "message": issue.message,
            "suggestion": issue.suggestion,
        }
        if issue.ai_suggestion is not None:
            entry["ai_suggestion"] = issue.ai_suggestion
        if issue.summary is not None:
            entry["summary"] = issue.summary
        if issue.difficulty is not None:
            entry["difficulty"] = issue.difficulty.value
        if issue.automation_pct is not None:
            entry["automation_pct"] = issue.automation_pct
        output["issues"]["warnings"].append(entry)
    for issue in report.assessment.info:
        output["issues"]["info"].append({
            "type": issue.type,
            "object": issue.object_name,
            "severity": issue.severity.value,
            "message": issue.message,
            "suggestion": issue.suggestion,
        })

    # Schema details (abbreviated for JSON — full detail in schema_inventory)
    for t in report.schema_inventory.tables:
        output["schema_details"]["tables"].append({
            "schema": t.table_schema,
            "name": t.table_name,
            "engine": t.engine,
            "rows": t.table_rows,
            "data_mb": round(t.data_length / 1024 / 1024, 2),
            "collation": t.table_collation,
        })
    for r in report.schema_inventory.routines:
        output["schema_details"]["stored_procedures"].append({
            "schema": r.routine_schema,
            "name": r.routine_name,
            "type": r.routine_type,
        })
    for tr in report.schema_inventory.triggers:
        output["schema_details"]["triggers"].append({
            "schema": tr.trigger_schema,
            "name": tr.trigger_name,
            "event": f"{tr.action_timing} {tr.event_manipulation}",
            "table": tr.event_object_table,
        })
    for v in report.schema_inventory.views:
        output["schema_details"]["views"].append({
            "schema": v.table_schema,
            "name": v.table_name,
        })
    for fk in report.schema_inventory.foreign_keys:
        output["schema_details"]["foreign_keys"].append({
            "schema": fk.constraint_schema,
            "table": fk.table_name,
            "name": fk.constraint_name,
            "references": f"{fk.referenced_table_schema}.{fk.referenced_table_name}",
        })

    # Full schema inventory (for convert/check)
    for t in report.schema_inventory.tables:
        output["schema_inventory"]["tables"].append(asdict(t))
    for c in report.schema_inventory.columns:
        output["schema_inventory"]["columns"].append(asdict(c))
    for idx in report.schema_inventory.indexes:
        output["schema_inventory"]["indexes"].append(asdict(idx))
    for fk in report.schema_inventory.foreign_keys:
        output["schema_inventory"]["foreign_keys"].append(asdict(fk))
    for r in report.schema_inventory.routines:
        output["schema_inventory"]["routines"].append(asdict(r))
    for tr in report.schema_inventory.triggers:
        output["schema_inventory"]["triggers"].append(asdict(tr))
    for v in report.schema_inventory.views:
        output["schema_inventory"]["views"].append(asdict(v))
    for e in report.schema_inventory.events:
        output["schema_inventory"]["events"].append(asdict(e))
    for p in report.schema_inventory.partitions:
        output["schema_inventory"]["partitions"].append(asdict(p))
    for cs in report.schema_inventory.charset_usage:
        output["schema_inventory"]["charset_usage"].append(asdict(cs))

    # Data profile
    for ts in report.data_profile.table_sizes[:20]:  # Top 20
        output["data_profile"]["largest_tables"].append({
            "schema": ts.table_schema,
            "table": ts.table_name,
            "rows": ts.table_rows,
            "data_mb": ts.data_mb,
            "total_mb": ts.total_mb,
        })
    for bc in report.data_profile.blob_columns:
        output["data_profile"]["blob_columns"].append({
            "schema": bc.table_schema,
            "table": bc.table_name,
            "column": bc.column_name,
            "type": bc.data_type,
        })

    if report.sp_analysis:
        for analysis in report.sp_analysis:
            output["sp_analysis"].append({
                "schema": analysis.routine_schema,
                "name": analysis.routine_name,
                "type": analysis.routine_type,
                "difficulty": analysis.difficulty.value,
                "automation_pct": analysis.automation_pct,
                "summary": analysis.summary,
                "suggested_approach": analysis.suggested_approach,
                "equivalent_code": analysis.equivalent_code,
                "tidb_compatible_sql": analysis.tidb_compatible_sql,
                "warnings": analysis.warnings,
                "complexity": {
                    "loc": analysis.complexity.loc,
                    "cursor_count": analysis.complexity.cursor_count,
                    "dynamic_sql_count": analysis.complexity.dynamic_sql_count,
                    "temp_table_count": analysis.complexity.temp_table_count,
                    "control_flow_count": analysis.complexity.control_flow_count,
                    "nested_calls": analysis.complexity.nested_calls,
                    "transaction_statements": analysis.complexity.transaction_statements,
                },
                "provider": analysis.provider,
                "model": analysis.model,
            })

    if report.cost_analysis is not None:
        output["cost_analysis"] = {
            "aurora_monthly_estimate": report.cost_analysis.aurora_monthly_estimate,
            "tidb_monthly_estimate": report.cost_analysis.tidb_monthly_estimate,
            "savings_pct": report.cost_analysis.savings_pct,
            "aurora_breakdown": {
                "compute": report.cost_analysis.aurora_breakdown.compute,
                "storage": report.cost_analysis.aurora_breakdown.storage,
                "io": report.cost_analysis.aurora_breakdown.io,
            },
            "tidb_recommendation": {
                "tier": report.cost_analysis.tidb_recommendation.tier,
                "nodes": report.cost_analysis.tidb_recommendation.nodes,
                "vcpu": report.cost_analysis.tidb_recommendation.vcpu,
                "ram_gb": report.cost_analysis.tidb_recommendation.ram_gb,
                "storage_gb": report.cost_analysis.tidb_recommendation.storage_gb,
            },
            "notes": report.cost_analysis.notes,
        }

    return output


def to_json_string(report: ScanReport, indent: int = 2) -> str:
    """Serialize ScanReport to a formatted JSON string."""
    data = generate_json_report(report)
    return json.dumps(data, indent=indent, default=_serialize)
