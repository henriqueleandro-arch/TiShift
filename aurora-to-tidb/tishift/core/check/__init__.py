"""Data validation and consistency checks."""

from tishift.core.check.table_checker import (
    compare_row_counts,
    compare_table_structures,
)

__all__ = ["compare_row_counts", "compare_table_structures"]
