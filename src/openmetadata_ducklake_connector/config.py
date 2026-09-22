from typing import Optional

from pydantic import BaseModel


class DuckLakeConnectionConfig(BaseModel):
    """Values passed through a Custom Database Service's connectionOptions.

    ducklake_attach_uri identifies the DuckLake catalog backend, e.g.
    "ducklake:postgres:dbname=ori_catalog" for a Postgres-backed catalog, or
    "ducklake:path/to/catalog.ducklake" for the file-based one. Match this to
    however the ORI DuckLake catalog is actually deployed before using it —
    it is not verified against a real deployment here.
    """

    ducklake_attach_uri: str
    ducklake_data_path: str
    catalog_alias: str = "ori_lake"
    s3_endpoint: Optional[str] = None
    s3_access_key_id: Optional[str] = None
    s3_secret_access_key: Optional[str] = None
