"""Best-effort SQL Server to TiDB collation mapping.

SQL Server collations combine code page, case sensitivity, accent sensitivity,
and sort rules into a single name.  TiDB supports utf8mb4 collations.
CI = case-insensitive, CS = case-sensitive.
"""

COLLATION_MAPPING: dict[str, str] = {
    # Latin / General
    "SQL_Latin1_General_CP1_CI_AS": "utf8mb4_general_ci",
    "SQL_Latin1_General_CP1_CS_AS": "utf8mb4_bin",
    "Latin1_General_CI_AS": "utf8mb4_general_ci",
    "Latin1_General_CS_AS": "utf8mb4_bin",
    "Latin1_General_100_CI_AS": "utf8mb4_general_ci",
    "Latin1_General_100_CS_AS": "utf8mb4_bin",
    "Latin1_General_100_CI_AS_SC": "utf8mb4_general_ci",
    "Latin1_General_BIN": "utf8mb4_bin",
    "Latin1_General_BIN2": "utf8mb4_bin",
    # Unicode
    "SQL_Latin1_General_CP1_CI_AI": "utf8mb4_general_ci",
    "Latin1_General_100_CI_AI": "utf8mb4_general_ci",
    # Asian
    "Japanese_CI_AS": "utf8mb4_general_ci",
    "Japanese_CS_AS": "utf8mb4_bin",
    "Chinese_PRC_CI_AS": "utf8mb4_general_ci",
    "Chinese_PRC_CS_AS": "utf8mb4_bin",
    "Korean_Wansung_CI_AS": "utf8mb4_general_ci",
    # TiDB default
    "utf8mb4_bin": "utf8mb4_bin",
    "utf8mb4_general_ci": "utf8mb4_general_ci",
    "utf8mb4_unicode_ci": "utf8mb4_unicode_ci",
}
