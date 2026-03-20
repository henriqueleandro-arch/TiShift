"""SQL Server to TiDB compatibility rules."""

BLOCKER_RULES: dict[str, str] = {
    "clr": "CLR assemblies/modules are not supported in TiDB.",
    "linked_server": "Linked servers and distributed queries must be redesigned.",
    "merge": "MERGE should be rewritten as deterministic INSERT/UPDATE/DELETE flows.",
    "for_xml": "FOR XML / OPENXML constructs are not supported.",
    "hierarchyid": "HIERARCHYID type is unsupported.",
    "spatial": "Spatial types/indexes require redesign.",
    "xml_type": "XML data type and methods require conversion.",
    "sql_variant": "SQL_VARIANT is unsupported.",
    "filestream": "FILESTREAM storage is unsupported.",
    "stored_procedure": "Stored procedures are parsed but not executed by TiDB.",
    "trigger": "Triggers are parsed but not executed by TiDB.",
    "udf": "SQL Server UDF behavior must be migrated to application code.",
    "cursor": "Server cursors should be rewritten.",
    "openquery": "OPENQUERY/OPENROWSET require architecture changes.",
    "service_broker": "Service Broker is unsupported.",
    "xp_cmdshell": "Extended stored procedures are unsupported.",
}

WARNING_RULES: dict[str, str] = {
    "identity": "IDENTITY behavior differs from TiDB AUTO_INCREMENT.",
    "computed_column": "Computed columns may need generated column rewrites.",
    "filtered_index": "Filtered indexes require alternative indexing strategy.",
    "columnstore": "Columnstore indexes are not equivalent in TiDB.",
    "temporal": "System-versioned temporal tables require custom history design.",
    "memory_optimized": "Memory optimized tables require redesign.",
    "cross_db_ref": "Cross-database references should be isolated.",
    "collation": "Collation differences can affect sorting/comparison semantics.",
    "agent_job": "SQL Server Agent jobs need external schedulers.",
    "instead_of_trigger": "INSTEAD OF trigger logic must move to app layer.",
    "sequence": "SEQUENCE behavior should be validated in TiDB.",
    "table_valued_param": "Table-valued parameters require API redesign.",
}

# --- TiDB Cloud tier-specific rules ---

STARTER_BLOCKERS: dict[str, str] = {
    "starter_storage_limit": "Data exceeds TiDB Cloud Starter 25 GiB free storage limit. Upgrade to Essential or Dedicated.",
    "starter_no_changefeed": "Changefeeds (TiCDC) are not available on Starter. CDC-based sync is not possible.",
    "starter_no_dm": "Data Migration (DM) is not available on Starter. Use cutover migration instead.",
    "starter_no_lightning": "TiDB Lightning is not available on Starter. Use ticloud CLI import instead.",
}

STARTER_WARNINGS: dict[str, str] = {
    "starter_connection_limit": "Starter tier allows max 400 concurrent connections (5,000 with spend limit).",
    "starter_import_size": "Starter import limited to 250 MiB per file via console. Use 'ticloud serverless import start' for larger files.",
    "starter_ru_budget": "Starter free tier includes 250M RUs/month. Heavy workloads may exceed this.",
    "starter_txn_timeout": "Starter transactions are killed after 30 minutes. Large LOAD DATA operations may need batching.",
}

ESSENTIAL_BLOCKERS: dict[str, str] = {
    "essential_no_dm": "Data Migration (DM) is not available on Essential. Use DMS or direct load.",
    "essential_no_lightning": "TiDB Lightning is not available on Essential. Use DMS for large loads or upgrade to Dedicated.",
}

ESSENTIAL_WARNINGS: dict[str, str] = {
    "essential_large_data": "Data exceeds 500 GB. Essential tier can handle this but Dedicated may offer better import performance.",
}
