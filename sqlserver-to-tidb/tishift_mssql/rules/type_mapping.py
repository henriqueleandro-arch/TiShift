"""Type mapping from SQL Server to TiDB (MySQL)."""

# Keys are lower-cased SQL Server types; values are TiDB (MySQL) equivalents.
# For types with length parameters (CHAR, VARCHAR, etc.), the length is
# preserved during conversion by the schema transformer — this map only
# records the base type change.

TYPE_MAPPING: dict[str, str] = {
    # -- Exact numeric --
    "bigint": "BIGINT",
    "int": "INT",
    "smallint": "SMALLINT",
    "tinyint": "TINYINT UNSIGNED",  # SQL Server TINYINT is 0-255
    "bit": "TINYINT(1)",
    "decimal": "DECIMAL",
    "numeric": "DECIMAL",
    "money": "DECIMAL(19,4)",
    "smallmoney": "DECIMAL(10,4)",
    # -- Approximate numeric --
    "float": "DOUBLE",
    "real": "FLOAT",
    # -- Date / time --
    "date": "DATE",
    "time": "TIME(6)",
    "datetime": "DATETIME",
    "datetime2": "DATETIME(6)",
    "smalldatetime": "DATETIME",
    "datetimeoffset": "VARCHAR(34)",
    # -- Character strings --
    "char": "CHAR",
    "nchar": "CHAR",
    "varchar": "VARCHAR",
    "nvarchar": "VARCHAR",
    "text": "LONGTEXT",
    "ntext": "LONGTEXT",
    "sysname": "VARCHAR(128)",
    # -- Binary strings --
    "binary": "BINARY",
    "varbinary": "VARBINARY",
    "image": "LONGBLOB",
    # -- Other --
    "xml": "LONGTEXT",
    "uniqueidentifier": "CHAR(36)",
    "rowversion": "BIGINT",
    "timestamp": "BIGINT",
    "sql_variant": "JSON",
    "hierarchyid": "VARCHAR(255)",
    "geography": "LONGTEXT",
    "geometry": "LONGTEXT",
}
