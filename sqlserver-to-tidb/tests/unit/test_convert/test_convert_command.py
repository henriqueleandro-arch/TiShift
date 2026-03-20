from __future__ import annotations

import json

from tishift_mssql.convert.command import run_convert


def test_run_convert_outputs_files(tmp_path) -> None:
    scan_report = {
        "schema_inventory": {
            "tables": [{"schema_name": "dbo", "table_name": "users"}],
            "columns": [{"schema_name": "dbo", "table_name": "users", "column_name": "id", "ordinal_position": 1, "data_type": "int", "is_nullable": False}],
            "indexes": [],
            "routines": [],
        }
    }
    report_path = tmp_path / "scan.json"
    report_path.write_text(json.dumps(scan_report))

    out_dir = tmp_path / "out"
    result = run_convert(
        config=None,
        scan_report_path=report_path,
        output_dir=out_dir,
        sp_only=False,
        schema_only=False,
        ai_enabled=False,
        language="python",
        apply=False,
        dry_run=False,
        schema_mapping="flatten",
        console=None,
    )

    assert result.schema_statements
    assert (out_dir / "schema" / "schema.sql").exists()
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "conversion-notes.md").exists()
