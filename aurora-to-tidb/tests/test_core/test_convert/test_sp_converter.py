"""Tests for stored procedure conversion."""

from __future__ import annotations

from tishift.core.convert.sp_converter import convert_stored_procedures


def test_convert_sp_skeleton(sample_inventory):
    results, ai = convert_stored_procedures(sample_inventory.routines, language="python", use_ai=False)
    assert ai == []
    assert results
    assert results[0].filename.endswith(".py")
    assert "Auto-generated" in results[0].code
