"""DuckDB -> OpenMetadata type mapping.

Kept separate from source.py so it can be unit-tested without the heavy
openmetadata-ingestion dependency installed.
"""

# Minimal starting map. DuckDB's DESCRIBE / duckdb_columns() can also report
# parameterised and nested types (VARCHAR(50), DECIMAL(18,3), STRUCT(...),
# LIST(...), MAP(...)) which are not handled here yet -- see the README
# "Known gaps" section. Values are plain strings, not the OpenMetadata
# DataType enum, so this module has no dependency on openmetadata-ingestion;
# source.py maps these strings to metadata.generated.schema.entity.data.table.DataType.
DUCKDB_TO_OM_TYPE_NAME = {
    "BIGINT": "BIGINT",
    "INTEGER": "INT",
    "SMALLINT": "SMALLINT",
    "TINYINT": "TINYINT",
    "VARCHAR": "VARCHAR",
    "DOUBLE": "DOUBLE",
    "FLOAT": "FLOAT",
    "BOOLEAN": "BOOLEAN",
    "DATE": "DATE",
    "TIMESTAMP": "TIMESTAMP",
    "TIME": "TIME",
    "BLOB": "BLOB",
}

UNKNOWN_TYPE_NAME = "UNKNOWN"


def base_type_name(duckdb_type: str) -> str:
    """Strip DuckDB's parameterised/nested type syntax down to a bare name.

    "VARCHAR(50)" -> "VARCHAR", "DECIMAL(18,3)" -> "DECIMAL",
    "STRUCT(a INTEGER, b VARCHAR)" -> "STRUCT". Does not attempt to parse
    the nested structure itself -- STRUCT/LIST/MAP columns will map to
    UNKNOWN_TYPE_NAME until nested-column support is added.
    """
    return duckdb_type.split("(")[0].strip().upper()


def to_openmetadata_type_name(duckdb_type: str) -> str:
    return DUCKDB_TO_OM_TYPE_NAME.get(base_type_name(duckdb_type), UNKNOWN_TYPE_NAME)
