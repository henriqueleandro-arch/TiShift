# T-SQL to MySQL/TiDB Function Mapping

Use this reference when converting views, rewriting queries, or generating application code stubs.

## Direct Function Translations

| T-SQL Function | MySQL/TiDB Equivalent | Notes |
|---|---|---|
| GETDATE() | NOW() | Current date+time |
| SYSDATETIME() | NOW() | Current date+time (microseconds via NOW(6)) |
| GETUTCDATE() | UTC_TIMESTAMP() | Current UTC date+time |
| ISNULL(a, b) | IFNULL(a, b) | Null coalescing |
| COALESCE(a, b, ...) | COALESCE(a, b, ...) | Same (ANSI SQL) |
| LEN(str) | CHAR_LENGTH(str) | Character count (not bytes) |
| DATALENGTH(str) | LENGTH(str) | Byte count (differs for multi-byte chars) |
| NEWID() | UUID() | Generate UUID string |
| DATEADD(unit, n, date) | TIMESTAMPADD(unit, n, date) | Date arithmetic |
| DATEDIFF(unit, d1, d2) | TIMESTAMPDIFF(unit, d1, d2) | Date difference |
| CHARINDEX(substr, str) | LOCATE(substr, str) | Find substring position (1-based) |
| SUBSTRING(str, start, len) | SUBSTRING(str, start, len) | Same syntax |
| LEFT(str, n) | LEFT(str, n) | Same |
| RIGHT(str, n) | RIGHT(str, n) | Same |
| LTRIM(str) | LTRIM(str) | Same |
| RTRIM(str) | RTRIM(str) | Same |
| UPPER(str) | UPPER(str) | Same |
| LOWER(str) | LOWER(str) | Same |
| REPLACE(str, old, new) | REPLACE(str, old, new) | Same |
| REVERSE(str) | REVERSE(str) | Same |
| REPLICATE(str, n) | REPEAT(str, n) | Repeat string n times |
| STUFF(str, start, len, new) | INSERT(str, start, len, new) | Replace substring |
| CONVERT(type, val) | CAST(val AS type) | Type casting (simplified) |
| TRY_CONVERT(type, val) | CAST(val AS type) | No error suppression in MySQL — wrap in application logic |
| CAST(val AS type) | CAST(val AS type) | Same (ANSI SQL) |
| IIF(cond, t, f) | IF(cond, t, f) | Ternary conditional |
| SUSER_SNAME() | CURRENT_USER() | Current user |
| FORMAT(val, fmt) | DATE_FORMAT(val, fmt) | Date formatting (format strings differ) |
| YEAR(date) | YEAR(date) | Same |
| MONTH(date) | MONTH(date) | Same |
| DAY(date) | DAY(date) | Same |
| ABS(n) | ABS(n) | Same |
| CEILING(n) | CEILING(n) | Same |
| FLOOR(n) | FLOOR(n) | Same |
| ROUND(n, d) | ROUND(n, d) | Same |
| POWER(n, p) | POWER(n, p) | Same |
| SQRT(n) | SQRT(n) | Same |

## Collation Mapping

| SQL Server Collation | TiDB Collation | Notes |
|---|---|---|
| SQL_Latin1_General_CP1_CI_AS | utf8mb4_general_ci | Default, case-insensitive |
| SQL_Latin1_General_CP1_CS_AS | utf8mb4_bin | Case-sensitive via binary |
| Latin1_General_CI_AS | utf8mb4_general_ci | |
| Latin1_General_CS_AS | utf8mb4_bin | |
| Latin1_General_100_CI_AS | utf8mb4_general_ci | SQL 2008+ |
| Latin1_General_100_CS_AS | utf8mb4_bin | |
| Latin1_General_100_CI_AS_SC | utf8mb4_general_ci | Supplementary character aware |
| Latin1_General_BIN / BIN2 | utf8mb4_bin | Binary collation |
| SQL_Latin1_General_CP1_CI_AI | utf8mb4_general_ci | Accent-insensitive (no exact equivalent) |
| Japanese_CI_AS | utf8mb4_general_ci | CJK |
| Japanese_CS_AS | utf8mb4_bin | CJK |
| Chinese_PRC_CI_AS | utf8mb4_general_ci | Simplified Chinese |
| Chinese_PRC_CS_AS | utf8mb4_bin | |
| Korean_Wansung_CI_AS | utf8mb4_general_ci | Korean |

**Key rule:** CI (case-insensitive) maps to `utf8mb4_general_ci`. CS (case-sensitive) or BIN maps to `utf8mb4_bin`.

**Warning:** Collation mapping is approximate. Accent sensitivity (AI/AS), kana sensitivity, and width sensitivity have no direct TiDB equivalents. Validate string comparison behavior after migration, especially for WHERE clauses and ORDER BY on text columns.

## No Direct Equivalent (Requires Redesign)

| T-SQL Feature | Why | Workaround |
|---|---|---|
| MERGE | Not in MySQL/TiDB dialect | Rewrite as INSERT ... ON DUPLICATE KEY UPDATE + DELETE |
| FOR XML PATH | No XML construction | Use JSON_OBJECT/JSON_ARRAY or application code |
| STRING_AGG (pre-2017) / FOR XML PATH string concat | Compatibility varies | Use GROUP_CONCAT() |
| CROSS APPLY | Lateral join syntax differs | Rewrite as LEFT JOIN with subquery or use LATERAL (TiDB 7.0+) |
| OUTER APPLY | Same as CROSS APPLY | Same approach |
| PIVOT / UNPIVOT | No native PIVOT | Use CASE + GROUP BY for pivot, UNION ALL for unpivot |
| TOP N | Different syntax | Use LIMIT N |
| OFFSET FETCH | Different syntax | Use LIMIT N OFFSET M |
| @@IDENTITY / SCOPE_IDENTITY() | Different function | Use LAST_INSERT_ID() |
| @@ROWCOUNT | Different variable | Use ROW_COUNT() |
| SET NOCOUNT ON | No equivalent needed | Omit (TiDB doesn't send row counts by default) |
| BEGIN TRY / CATCH | No structured error handling in SQL | Move error handling to application code |
| RAISERROR / THROW | No equivalent | Use SIGNAL SQLSTATE in stored procedures (but SPs don't execute anyway) |
