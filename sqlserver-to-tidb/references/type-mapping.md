# SQL Server to TiDB Type Mapping Reference

## Table of Contents
1. [Numeric Types](#numeric-types)
2. [Date/Time Types](#datetime-types)
3. [String Types](#string-types)
4. [Binary Types](#binary-types)
5. [Special Types](#special-types)
6. [Length and Precision Handling](#length-and-precision-handling)

---

## Numeric Types

| SQL Server | TiDB | Notes |
|---|---|---|
| bigint | BIGINT | Direct equivalent |
| int | INT | Direct equivalent |
| smallint | SMALLINT | Direct equivalent |
| tinyint | TINYINT UNSIGNED | SQL Server tinyint is 0-255 (unsigned) |
| bit | TINYINT(1) | Boolean representation |
| decimal(p,s) | DECIMAL(p,s) | Preserve precision and scale exactly |
| numeric(p,s) | DECIMAL(p,s) | Alias for decimal |
| money | DECIMAL(19,4) | Fixed scale for currency |
| smallmoney | DECIMAL(10,4) | Fixed scale for currency |
| float | DOUBLE | Approximate numeric, 8 bytes |
| real | FLOAT | Approximate numeric, 4 bytes |

## Date/Time Types

| SQL Server | TiDB | Notes |
|---|---|---|
| date | DATE | Direct equivalent |
| time | TIME(6) | Up to microsecond precision |
| datetime | DATETIME | Seconds precision only |
| datetime2(p) | DATETIME(MIN(p,6)) | Cap fractional seconds at 6 (microseconds). SQL Server supports up to 7 (100ns) but TiDB max is 6 |
| smalldatetime | DATETIME | Seconds precision |
| datetimeoffset | VARCHAR(34) | No timezone-aware type in TiDB. Add COMMENT 'was: datetimeoffset'. Application must handle TZ conversion |

## String Types

| SQL Server | TiDB | Notes |
|---|---|---|
| char(n) | CHAR(n) | Fixed-length, preserve n |
| nchar(n) | CHAR(n) | TiDB uses utf8mb4, so nchar distinction unnecessary |
| varchar(n) | VARCHAR(n) | Variable-length, preserve n |
| nvarchar(n) | VARCHAR(n) | TiDB uses utf8mb4 natively |
| varchar(max) | LONGTEXT | -1 length means MAX |
| nvarchar(max) | LONGTEXT | -1 length means MAX |
| text | LONGTEXT | Deprecated in SQL Server, unbounded |
| ntext | LONGTEXT | Deprecated in SQL Server, unbounded |
| sysname | VARCHAR(128) | SQL Server internal type for object names |

## Binary Types

| SQL Server | TiDB | Notes |
|---|---|---|
| binary(n) | BINARY(n) | Fixed-length, preserve n |
| varbinary(n) | VARBINARY(n) | Variable-length, preserve n |
| varbinary(max) | LONGBLOB | -1 length means MAX |
| image | LONGBLOB | Deprecated, large binary |

## Special Types

| SQL Server | TiDB | Conversion Notes |
|---|---|---|
| uniqueidentifier | CHAR(36) | UUID stored as string. Use UUID() for generation |
| rowversion / timestamp | BIGINT | No auto-versioning in TiDB. Add COMMENT 'was: rowversion' |
| xml | LONGTEXT | No XML type or XPath functions. Add COMMENT 'was: xml'. Port XML queries to application |
| geography | LONGTEXT | No spatial index or ST_* functions. Add COMMENT 'was: spatial' |
| geometry | LONGTEXT | No spatial index or ST_* functions. Add COMMENT 'was: spatial' |
| hierarchyid | VARCHAR(255) | No hierarchy support. Add COMMENT 'was: hierarchyid'. Implement tree traversal in application |
| sql_variant | JSON | Type metadata is lost. Add COMMENT 'was: sql_variant' |

## Length and Precision Handling

**varchar/nvarchar(n):** Preserve n if n > 0. If n = -1 (MAX), map to LONGTEXT.

**binary/varbinary(n):** Preserve n if n > 0. If n = -1 (MAX), map to LONGBLOB.

**decimal(p,s):** Preserve both precision and scale exactly. TiDB supports up to DECIMAL(65,30).

**datetime2(p):** Map fractional seconds precision: `DATETIME(MIN(MAX(p,0), 6))`. This caps at microseconds since TiDB doesn't support 100-nanosecond precision.

**nchar/nvarchar:** The `n` prefix is irrelevant for TiDB since utf8mb4 handles all Unicode. Divide SQL Server's max_length by 2 to get the character count (SQL Server stores nchar as 2 bytes per char).
