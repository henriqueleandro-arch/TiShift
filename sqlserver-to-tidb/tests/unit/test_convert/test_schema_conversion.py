from __future__ import annotations

from tishift_mssql.convert.schema import generate_schema_ddl, map_table_name


def _scan_payload() -> dict[str, object]:
    return {
        "schema_inventory": {
            "tables": [
                {"schema_name": "dbo", "table_name": "users"},
                {"schema_name": "sales", "table_name": "users"},
            ],
            "columns": [
                {
                    "schema_name": "dbo",
                    "table_name": "users",
                    "column_name": "id",
                    "ordinal_position": 1,
                    "data_type": "int",
                    "is_nullable": False,
                    "is_identity": True,
                },
                {
                    "schema_name": "dbo",
                    "table_name": "users",
                    "column_name": "name",
                    "ordinal_position": 2,
                    "data_type": "nvarchar",
                    "max_length": 100,
                    "is_nullable": False,
                },
                {
                    "schema_name": "sales",
                    "table_name": "users",
                    "column_name": "id",
                    "ordinal_position": 1,
                    "data_type": "int",
                    "is_nullable": False,
                },
            ],
            "indexes": [
                {
                    "schema_name": "dbo",
                    "table_name": "users",
                    "is_primary_key": True,
                    "columns": "id",
                }
            ],
        }
    }


def test_map_table_name_modes() -> None:
    assert map_table_name("dbo", "users", "flatten") == (None, "users")
    assert map_table_name("sales", "users", "prefix") == (None, "sales_users")
    assert map_table_name("sales", "users", "database") == ("sales", "users")


def test_generate_schema_ddl_detects_collision_in_flatten() -> None:
    ddl, warnings = generate_schema_ddl(_scan_payload(), "flatten")
    assert ddl
    assert any("Name collision" in warning for warning in warnings)
    assert "AUTO_INCREMENT" in ddl[0]
