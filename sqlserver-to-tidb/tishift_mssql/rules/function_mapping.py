"""Function-level translations from T-SQL to TiDB/MySQL."""

FUNCTION_MAPPING: dict[str, str] = {
    "GETDATE": "NOW",
    "SYSDATETIME": "NOW",
    "ISNULL": "IFNULL",
    "LEN": "CHAR_LENGTH",
    "DATALENGTH": "LENGTH",
    "NEWID": "UUID",
    "DATEADD": "TIMESTAMPADD",
    "DATEDIFF": "TIMESTAMPDIFF",
    "CHARINDEX": "LOCATE",
    "SUBSTRING": "SUBSTRING",
    "CONVERT": "CAST",
    "TRY_CONVERT": "CAST",
    "IIF": "IF",
    "SUSER_SNAME": "CURRENT_USER",
}
