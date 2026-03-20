"""Tests for schema transformer."""

from __future__ import annotations

from tishift.core.convert.schema_transformer import transform_schema


def test_transform_schema_basic(sample_inventory):
    result = transform_schema(sample_inventory)
    assert "CREATE TABLE" in result.create_tables_sql
    assert "ENGINE=InnoDB" in result.create_tables_sql
