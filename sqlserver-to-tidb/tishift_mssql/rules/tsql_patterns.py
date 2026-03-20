"""Compiled regex patterns for SQL Server feature detection."""

from __future__ import annotations

import re

TSQL_PATTERNS: dict[str, re.Pattern[str]] = {
    "merge": re.compile(r"\bMERGE\b", re.IGNORECASE),
    "for_xml": re.compile(r"\bFOR\s+XML\b", re.IGNORECASE),
    "openxml": re.compile(r"\bOPENXML\b", re.IGNORECASE),
    "cross_apply": re.compile(r"\bCROSS\s+APPLY\b", re.IGNORECASE),
    "outer_apply": re.compile(r"\bOUTER\s+APPLY\b", re.IGNORECASE),
    "pivot": re.compile(r"\bPIVOT\b", re.IGNORECASE),
    "unpivot": re.compile(r"\bUNPIVOT\b", re.IGNORECASE),
    "cursor": re.compile(r"\bCURSOR\b", re.IGNORECASE),
    "sp_executesql": re.compile(r"\bsp_executesql\b", re.IGNORECASE),
    "nolock": re.compile(r"\bNOLOCK\b", re.IGNORECASE),
    "openquery": re.compile(r"\bOPENQUERY\b", re.IGNORECASE),
    "openrowset": re.compile(r"\bOPENROWSET\b", re.IGNORECASE),
    "raiserror": re.compile(r"\bRAISERROR\b", re.IGNORECASE),
    "throw": re.compile(r"\bTHROW\b", re.IGNORECASE),
    "try_catch": re.compile(r"\bBEGIN\s+TRY\b", re.IGNORECASE),
    "transaction": re.compile(r"\bBEGIN\s+TRAN\b", re.IGNORECASE),
    "table_valued_param": re.compile(r"\bREADONLY\b", re.IGNORECASE),
    "temp_table": re.compile(r"#\w+", re.IGNORECASE),
    "hint_option": re.compile(r"\bOPTION\s*\(", re.IGNORECASE),
    "output_clause": re.compile(r"\bOUTPUT\b", re.IGNORECASE),
    "identity_fn": re.compile(r"\b(SCOPE_IDENTITY|@@IDENTITY|IDENT_CURRENT)\b", re.IGNORECASE),
    "sequence": re.compile(r"\bNEXT\s+VALUE\s+FOR\b", re.IGNORECASE),
    "service_broker": re.compile(r"\bBEGIN\s+DIALOG\b|\bSEND\s+ON\s+CONVERSATION\b", re.IGNORECASE),
    "xml_methods": re.compile(r"\b(nodes|value|query|exist|modify)\s*\(", re.IGNORECASE),
    "merge_hint": re.compile(r"\bHOLDLOCK\b", re.IGNORECASE),
}
