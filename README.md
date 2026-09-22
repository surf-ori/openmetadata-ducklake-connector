# openmetadata-ducklake-connector

A custom [OpenMetadata](https://open-metadata.org/) source connector for the
[ORI DuckLake](https://github.com/surf-ori/ori-data-mesh-architecture)
catalog. Written up alongside
[surf-ori/ori-data-mesh-architecture](https://github.com/surf-ori/ori-data-mesh-architecture)
as an exploration of what it'd take to get OpenMetadata reading the lake's
own table/column metadata, rather than only what dbt's `manifest.json`
already tells it.

**Status: exploratory sketch, not production-ready.** See "What's been
validated" and "Known gaps" below before relying on this for anything.

## Target versions

Checked against PyPI on 2026-09-22, the date this was written:

- **`openmetadata-ingestion` 2.0.2.0** — the latest release, and what this
  connector's imports and entity/config wiring were actually validated
  against (see "What's been validated"). `pyproject.toml` floors on
  `>=2.0.0` because the `Source`/`_iter()` interface it targets doesn't
  match older 1.x releases' `api.source.Source`/`next_record()` shape.
- **`duckdb` 1.5.5** — the latest release, and the version the SQL in
  "What's been validated" was actually run against.
- **DuckLake format spec v1.0** (released April 2026, production-ready
  with guaranteed backward-compatibility — see the
  [announcement](https://ducklake.select/2026/04/13/ducklake-10/)). A
  v1.1 standard was reportedly expected around September 2026, but I
  could not confirm it has shipped; re-check before assuming v1.1 features
  are available. The `ducklake` DuckDB extension itself is MIT-licensed,
  same as the spec.

## What it does

`DuckLakeSource` attaches to the DuckLake catalog directly (via DuckDB's
`ducklake` extension) rather than treating it as a bare `.duckdb` file. It
walks the catalog's schemas, tables and columns, and reads each column's
`comment` — which is where `datacontract export` (or an equivalent
`COMMENT ON COLUMN` step) already writes the field's description from its
ODCS contract — so descriptions arrive in OpenMetadata pre-filled instead of
needing re-entry in its UI.

## What's been validated

Everything below was actually run and checked in this session, against
`openmetadata-ingestion==2.0.2.0`:

- The package imports cleanly against the real `openmetadata-ingestion`
  library (this caught one real bug: `Entity` lives in
  `metadata.ingestion.api.models`, not `metadata.ingestion.models.topology`
  as an earlier draft assumed — fixed).
- `DuckLakeSource` is a concrete `Source` subclass with no unimplemented
  abstract methods.
- `CreateDatabaseRequest`, `CreateDatabaseSchemaRequest`, `CreateTableRequest`
  and `Column` all accept the field names and values this connector passes
  them (`name`, `service`, `database`, `databaseSchema`, `dataType`,
  `dataTypeDisplay`, `description`).
- The nested config path a Custom Database Service actually hands a
  connector — `serviceConnection.root.config.connectionOptions.root` — was
  round-tripped through a real `WorkflowSource.model_validate(...)` call and
  resolves to a plain dict, matching what `DuckLakeSource.__init__` expects.
- The DuckDB SQL this connector runs (`information_schema.schemata`,
  `information_schema.tables`, `duckdb_columns()` including its `comment`
  field after a `COMMENT ON COLUMN ...`) was run against a real, plain
  DuckDB database and returns exactly what the connector assumes.

## Known gaps

- **Not tested against an actual DuckLake catalog.** The `ducklake` DuckDB
  extension downloads over plain HTTP, which this development sandbox's
  network policy blocks (`403`, non-CONNECT request refused by the egress
  proxy). The plain-DuckDB SQL above was validated; the catalog-qualified
  version (`{catalog}.information_schema...` after `ATTACH 'ducklake:...'`)
  was not. Try this against a real DuckLake catalog before trusting it.
- **Not tested against a live OpenMetadata server.** Nothing here has
  actually been registered as a Custom Database Service and run through a
  real ingestion workflow yet.
- **Nested types aren't mapped.** `STRUCT`, `LIST` and `MAP` columns (which
  the ORI DuckLake uses — see the blog's note on unnesting) currently fall
  back to `DataType.UNKNOWN` instead of `Column.children`. See
  `type_mapping.py`.
- **Table-level descriptions still missing.** Only column-level
  descriptions from contract-derived comments are wired in; table
  docstrings are not. (Column-level *lineage* now has a starting point —
  see "OpenLineage lineage layer" below — but it hasn't been run either.)
- **Version-sensitive.** This targets OpenMetadata's current
  `metadata.ingestion.api.steps.Source` / `_iter()` interface. Older
  releases used `metadata.ingestion.api.source.Source` with
  `next_record()` instead.

## Development

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/
```

The unit tests only exercise `type_mapping.py`, which has no dependency on
`openmetadata-ingestion` (a heavy, separately-pinned dependency tree).
Install it explicitly to work on `source.py` itself:

```bash
.venv/bin/pip install -e ".[openmetadata]"
```

## Configuration

See [`configs/ducklake_ingestion.example.yaml`](configs/ducklake_ingestion.example.yaml)
for a full ingestion config. Register it in OpenMetadata as a
`Database Services → Add New Service → Custom` service, with
`sourcePythonClass: openmetadata_ducklake_connector.source.DuckLakeSource`.

## OpenLineage lineage layer (sketch)

`DuckLakeSource` catalogs the lake's tables and columns; it does not know
which model fed which. A separate, complementary piece —
[`openlineage_config.py`](src/openmetadata_ducklake_connector/openlineage_config.py)
— sketches the other half: getting column-level lineage from `dbt-ol`
(OpenLineage's drop-in replacement for the `dbt` command, which does
support the `duckdb` adapter) into OpenMetadata.

**The finding that shapes this:** OpenMetadata's OpenLineage pipeline
service is read-only for table resolution (tables/schemas/databases must
already exist — hence needing `DuckLakeSource` or the dbt-manifest workflow
first), *and* it currently consumes events from a message broker — Kafka,
Kinesis, or NATS JetStream — not a plain HTTP POST the way Marquez accepts
them. See the
[OpenLineage connector docs](https://docs.open-metadata.org/v1.12.x/connectors/pipeline/openlineage)
and the
[NATS JetStream feature request](https://github.com/open-metadata/OpenMetadata/issues/33664)
that confirms Kafka/Kinesis are the two existing options. That's a real
infrastructure decision for a stack whose whole pitch is "no database
servers to babysit": adding lineage this way means running (or paying for)
a Kafka topic, not just pointing an env var at a URL.

What's here: `OpenLineageKafkaConfig` and `write_openlineage_yaml()`
generate the `openlineage.yml` that `dbt-ol` reads, pointed at that Kafka
topic — tested (`pytest tests/test_openlineage_config.py`) only in the sense
that the YAML it produces round-trips through `yaml.safe_load` with the
right shape. Not included, and not sketched yet:

- OpenMetadata's own ingestion-workflow config for the *consuming* side
  (its `brokerConfig`) — this only covers the producer side.
- Actually running `dbt-ol build` against a Kafka broker and confirming
  lineage events arrive and attach to tables `DuckLakeSource` already
  registered.
- Whether the built-in OpenLineage SQL parser handles DuckDB-specific
  syntax (struct/list unnesting) well enough, or whether the sqlglot-based
  approach in
  [oluies/duckdb-openmetadata-lineage](https://github.com/oluies/duckdb-openmetadata-lineage)
  is needed instead.

Given the Kafka requirement, it's worth deciding whether column-level
lineage is actually needed before standing this up — the dbt-manifest
workflow already gives model-level lineage for free, with nothing extra to
run.

## License

[EUPL 1.2](LICENSE) — the current official version of the European Union
Public Licence (there is no 1.3).
