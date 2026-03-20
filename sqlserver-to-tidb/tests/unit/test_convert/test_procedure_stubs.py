from __future__ import annotations

from tishift_mssql.convert.procedures import generate_procedure_stubs


def test_generate_procedure_stubs(tmp_path) -> None:
    scan_report = {
        "schema_inventory": {
            "routines": [
                {
                    "schema_name": "dbo",
                    "routine_name": "sp_upsert_user",
                    "routine_type": "SQL_STORED_PROCEDURE",
                    "definition": "SELECT 1",
                }
            ]
        }
    }
    artifacts = generate_procedure_stubs(scan_report, tmp_path, "python", ai_enabled=True)
    assert len(artifacts) == 1
    assert artifacts[0].path.exists()
    assert "AI-assisted" in artifacts[0].path.read_text()
