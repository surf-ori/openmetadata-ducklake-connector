"""Custom OpenMetadata connector for the ORI DuckLake.

STATUS: exploratory sketch, not run against a live OpenMetadata server or a
real DuckLake catalog. See the README "Known gaps" section before relying
on this for anything.

Attaches to the DuckLake catalog directly (not a bare DuckDB file), walks its
schemas/tables/columns, and reuses the column comments that `datacontract`
already writes into the catalog from our ODCS contracts, so descriptions
don't need re-entry in OpenMetadata's UI.

This targets OpenMetadata's current `metadata.ingestion.api.steps.Source` /
`_iter()` interface. Older OpenMetadata releases used
`metadata.ingestion.api.source.Source` with `next_record()` instead -- check
which one your target version expects before deploying this.
"""

from typing import Iterable, Optional

import duckdb

from metadata.generated.schema.api.data.createDatabase import CreateDatabaseRequest
from metadata.generated.schema.api.data.createDatabaseSchema import (
    CreateDatabaseSchemaRequest,
)
from metadata.generated.schema.api.data.createTable import CreateTableRequest
from metadata.generated.schema.entity.data.table import Column, DataType, TableType
from metadata.generated.schema.metadataIngestion.workflow import (
    Source as WorkflowSource,
)
from metadata.ingestion.api.models import Either, Entity
from metadata.ingestion.api.steps import Source
from metadata.ingestion.ometa.ometa_api import OpenMetadata

from openmetadata_ducklake_connector.config import DuckLakeConnectionConfig
from openmetadata_ducklake_connector.type_mapping import (
    UNKNOWN_TYPE_NAME,
    to_openmetadata_type_name,
)


class DuckLakeSource(Source):
    """Reads the ORI DuckLake catalog and yields it as OpenMetadata entities."""

    def __init__(self, config: WorkflowSource, metadata: OpenMetadata):
        self.config = config
        self.metadata = metadata
        # `connectionOptions` on a Custom Database Service arrives as a flat
        # dict; validate it into our own config model.
        self.lake_config = DuckLakeConnectionConfig(
            **config.serviceConnection.root.config.connectionOptions.root
        )
        self.service_name = config.serviceName
        self.connection: Optional[duckdb.DuckDBPyConnection] = None

    @classmethod
    def create(cls, config_dict: dict, metadata: OpenMetadata) -> "DuckLakeSource":
        config = WorkflowSource.model_validate(config_dict)
        return cls(config, metadata)

    def prepare(self):
        self.connection = duckdb.connect()
        self.connection.execute("INSTALL ducklake; LOAD ducklake;")
        if self.lake_config.s3_endpoint:
            self.connection.execute("INSTALL httpfs; LOAD httpfs;")
            self.connection.execute(
                f"""
                CREATE SECRET (
                    TYPE s3,
                    ENDPOINT '{self.lake_config.s3_endpoint}',
                    KEY_ID '{self.lake_config.s3_access_key_id}',
                    SECRET '{self.lake_config.s3_secret_access_key}'
                );
                """
            )
        self.connection.execute(
            f"""
            ATTACH '{self.lake_config.ducklake_attach_uri}'
            AS {self.lake_config.catalog_alias}
            (DATA_PATH '{self.lake_config.ducklake_data_path}');
            """
        )

    def test_connection(self) -> None:
        self.connection.execute(
            f"SELECT 1 FROM {self.lake_config.catalog_alias}.information_schema.schemata LIMIT 1"
        )

    def _iter(self) -> Iterable[Either[Entity]]:
        catalog = self.lake_config.catalog_alias

        yield Either(
            right=CreateDatabaseRequest(
                name=catalog,
                service=self.service_name,
            )
        )

        schemas = self.connection.execute(
            f"""
            SELECT schema_name FROM {catalog}.information_schema.schemata
            WHERE schema_name NOT IN ('information_schema', 'main')
            """
        ).fetchall()

        for (schema_name,) in schemas:
            yield Either(
                right=CreateDatabaseSchemaRequest(
                    name=schema_name,
                    database=f"{self.service_name}.{catalog}",
                )
            )

            tables = self.connection.execute(
                f"""
                SELECT table_name FROM {catalog}.information_schema.tables
                WHERE table_schema = '{schema_name}'
                """
            ).fetchall()

            for (table_name,) in tables:
                # duckdb_columns() exposes per-column `comment`, which is
                # where `datacontract export` (or an equivalent COMMENT ON
                # COLUMN step) already writes each field's description from
                # the ODCS contract -- so it rides along for free here.
                columns = self.connection.execute(
                    f"""
                    SELECT column_name, data_type, comment
                    FROM duckdb_columns()
                    WHERE database_name = '{catalog}'
                      AND schema_name = '{schema_name}'
                      AND table_name = '{table_name}'
                    ORDER BY column_index
                    """
                ).fetchall()

                yield Either(
                    right=CreateTableRequest(
                        name=table_name,
                        tableType=TableType.Regular,
                        databaseSchema=f"{self.service_name}.{catalog}.{schema_name}",
                        columns=[
                            Column(
                                name=col_name,
                                dataType=DataType(to_openmetadata_type_name(col_type))
                                if to_openmetadata_type_name(col_type) != UNKNOWN_TYPE_NAME
                                else DataType.UNKNOWN,
                                dataTypeDisplay=col_type,
                                description=comment or None,
                            )
                            for col_name, col_type, comment in columns
                        ],
                    )
                )

    def close(self) -> None:
        if self.connection:
            self.connection.close()
