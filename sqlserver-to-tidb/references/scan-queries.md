# Phase 2 Scan Queries

Exact SQL for each of the 15 scan steps. Substitute `$DB` with the user's database name. Wrap each in `sqlcmd -S $HOST -U $USER -P $PASS -d $DB -Q "..."`.

For steps that return large text columns (especially Step 2.5 stored procedure definitions), add `-y 0` to `sqlcmd` to prevent output truncation. Without this flag, sqlcmd truncates text columns at 256 characters by default, which will cut off stored procedure and trigger definitions.

For SQL Server 2016 and earlier, `STRING_AGG` is not available — see the [version fallbacks](#version-fallbacks) section at the bottom.

---

## Step 2.1 — Tables

```sql
SELECT s.name AS schema_name, t.name AS table_name, p.rows,
  CAST(ROUND(SUM(a.total_pages) * 8.0 / 1024, 2) AS DECIMAL(18,2)) AS size_mb,
  t.is_memory_optimized, t.temporal_type,
  CASE WHEN NOT EXISTS(
    SELECT 1 FROM sys.indexes i WHERE i.object_id = t.object_id AND i.type IN (1,5)
  ) THEN 1 ELSE 0 END AS is_heap
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
JOIN sys.allocation_units a ON p.partition_id = a.container_id
GROUP BY s.name, t.name, p.rows, t.is_memory_optimized, t.temporal_type, t.object_id
ORDER BY p.rows DESC
```

## Step 2.2 — Columns

```sql
SELECT s.name AS schema_name, t.name AS table_name, c.name AS column_name,
  tp.name AS type_name, c.max_length, c.precision, c.scale, c.is_nullable,
  c.is_identity, c.is_computed, c.collation_name,
  CASE WHEN cc.object_id IS NOT NULL THEN cc.definition ELSE NULL END AS computed_definition,
  CASE WHEN dc.object_id IS NOT NULL THEN dc.definition ELSE NULL END AS default_value,
  CASE WHEN tp.name = 'varbinary' AND c.max_length = -1
    AND EXISTS(SELECT 1 FROM sys.columns fc
      JOIN sys.tables ft ON fc.object_id = ft.object_id
      WHERE fc.is_filestream = 1 AND fc.column_id = c.column_id AND ft.object_id = t.object_id)
    THEN 1 ELSE 0 END AS is_filestream
FROM sys.columns c
JOIN sys.tables t ON c.object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.types tp ON c.user_type_id = tp.user_type_id
LEFT JOIN sys.computed_columns cc ON c.object_id = cc.object_id AND c.column_id = cc.column_id
LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
ORDER BY s.name, t.name, c.column_id
```

## Step 2.3 — Indexes

```sql
SELECT s.name AS schema_name, t.name AS table_name, i.name AS index_name,
  i.type_desc, i.is_unique, i.is_primary_key, i.has_filter, i.filter_definition,
  STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS columns
FROM sys.indexes i
JOIN sys.tables t ON i.object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
WHERE i.type > 0
GROUP BY s.name, t.name, i.name, i.type_desc, i.is_unique, i.is_primary_key, i.has_filter, i.filter_definition
ORDER BY s.name, t.name, i.name
```

## Step 2.4 — Foreign Keys

```sql
SELECT s.name AS schema_name, t.name AS table_name, fk.name AS fk_name,
  rs.name AS ref_schema, rt.name AS ref_table,
  fk.delete_referential_action_desc AS on_delete,
  fk.update_referential_action_desc AS on_update,
  STRING_AGG(pc.name, ', ') WITHIN GROUP (ORDER BY fkc.constraint_column_id) AS columns,
  STRING_AGG(rc.name, ', ') WITHIN GROUP (ORDER BY fkc.constraint_column_id) AS ref_columns
FROM sys.foreign_keys fk
JOIN sys.tables t ON fk.parent_object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.tables rt ON fk.referenced_object_id = rt.object_id
JOIN sys.schemas rs ON rt.schema_id = rs.schema_id
JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
JOIN sys.columns pc ON fkc.parent_object_id = pc.object_id AND fkc.parent_column_id = pc.column_id
JOIN sys.columns rc ON fkc.referenced_object_id = rc.object_id AND fkc.referenced_column_id = rc.column_id
GROUP BY s.name, t.name, fk.name, rs.name, rt.name,
  fk.delete_referential_action_desc, fk.update_referential_action_desc
ORDER BY s.name, t.name, fk.name
```

## Step 2.5 — Stored Procedures and Functions

```sql
SELECT s.name AS schema_name, o.name AS routine_name,
  o.type_desc,
  CASE WHEN am.object_id IS NOT NULL THEN 1 ELSE 0 END AS is_clr,
  LEN(m.definition) AS definition_length,
  m.definition
FROM sys.objects o
JOIN sys.schemas s ON o.schema_id = s.schema_id
LEFT JOIN sys.sql_modules m ON o.object_id = m.object_id
LEFT JOIN sys.assembly_modules am ON o.object_id = am.object_id
WHERE o.type IN ('P', 'FN', 'IF', 'TF')
ORDER BY o.type_desc, s.name, o.name
```

## Step 2.6 — Triggers

```sql
SELECT s.name AS schema_name, OBJECT_NAME(tr.parent_id) AS table_name,
  tr.name AS trigger_name, tr.is_instead_of_trigger,
  m.definition
FROM sys.triggers tr
JOIN sys.tables t ON tr.parent_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
LEFT JOIN sys.sql_modules m ON tr.object_id = m.object_id
WHERE tr.parent_class = 1
ORDER BY s.name, table_name, tr.name
```

## Step 2.7 — Views

```sql
SELECT s.name AS schema_name, v.name AS view_name,
  CASE WHEN EXISTS(
    SELECT 1 FROM sys.indexes i WHERE i.object_id = v.object_id AND i.type = 1
  ) THEN 1 ELSE 0 END AS is_indexed,
  m.definition
FROM sys.views v
JOIN sys.schemas s ON v.schema_id = s.schema_id
LEFT JOIN sys.sql_modules m ON v.object_id = m.object_id
ORDER BY s.name, v.name
```

## Step 2.8 — CLR Assemblies

```sql
SELECT a.name AS assembly_name, a.permission_set_desc,
  a.clr_name, a.create_date
FROM sys.assemblies a
WHERE a.is_user_defined = 1
ORDER BY a.name
```

## Step 2.9 — Linked Servers

```sql
SELECT s.name AS server_name, s.product, s.provider, s.data_source,
  s.is_linked, s.is_remote_login_enabled
FROM sys.servers s
WHERE s.is_linked = 1
ORDER BY s.name
```

## Step 2.10 — SQL Agent Jobs

```sql
SELECT j.name AS job_name, j.enabled, j.date_created,
  js.step_name, js.subsystem, js.command
FROM msdb.dbo.sysjobs j
JOIN msdb.dbo.sysjobsteps js ON j.job_id = js.job_id
ORDER BY j.name, js.step_id
```

## Step 2.11 — Collation Usage

```sql
SELECT c.collation_name, COUNT(*) AS column_count
FROM sys.columns c
JOIN sys.tables t ON c.object_id = t.object_id
WHERE c.collation_name IS NOT NULL
GROUP BY c.collation_name
ORDER BY column_count DESC
```

## Step 2.12 — Data Profile

```sql
SELECT s.name AS schema_name, t.name AS table_name,
  SUM(p.rows) AS row_count,
  CAST(ROUND(SUM(a.total_pages) * 8.0 / 1024, 2) AS DECIMAL(18,2)) AS size_mb
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.dm_db_partition_stats p ON t.object_id = p.object_id AND p.index_id IN (0,1)
JOIN sys.allocation_units a ON p.partition_id = a.container_id
GROUP BY s.name, t.name
ORDER BY size_mb DESC
```

## Step 2.13 — Server Metadata

```sql
SELECT @@VERSION AS full_version,
  SERVERPROPERTY('ProductVersion') AS product_version,
  SERVERPROPERTY('Edition') AS edition,
  SERVERPROPERTY('IsIntegratedSecurityOnly') AS windows_auth_only,
  SERVERPROPERTY('Collation') AS server_collation
```

## Step 2.14 — CDC Status

```sql
SELECT name AS database_name, is_cdc_enabled
FROM sys.databases
WHERE name = DB_NAME()
```

## Step 2.15 — SSIS Presence

```sql
SELECT CASE WHEN DB_ID('SSISDB') IS NOT NULL THEN 1 ELSE 0 END AS has_ssis
```

---

## Version Fallbacks

`STRING_AGG` requires SQL Server 2017+. For SQL Server 2016 and earlier, replace `STRING_AGG(col, ', ')` with the `FOR XML PATH` pattern:

```sql
-- Instead of: STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS columns
-- Use:
STUFF((
  SELECT ', ' + c2.name
  FROM sys.index_columns ic2
  JOIN sys.columns c2 ON ic2.object_id = c2.object_id AND ic2.column_id = c2.column_id
  WHERE ic2.object_id = i.object_id AND ic2.index_id = i.index_id
  ORDER BY ic2.key_ordinal
  FOR XML PATH('')
), 1, 2, '') AS columns
```

This affects Steps 2.3 (indexes) and 2.4 (foreign keys). Check the SQL Server version from Step 2.13 output — if the major version is < 14 (SQL Server 2017), use the fallback.

Other catalog view compatibility notes:
- `is_memory_optimized` (Step 2.1): available from SQL Server 2014+. For 2012, remove this column and set `has_memory_optimized = false` in the checklist.
- `temporal_type` (Step 2.1): available from SQL Server 2016+. For 2014 and earlier, remove this column and set `has_temporal_tables = false`.
- `is_filestream` (Step 2.2): available from SQL Server 2008+. Should be present in all supported versions.
