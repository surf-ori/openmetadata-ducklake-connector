from openmetadata_ducklake_connector.type_mapping import (
    UNKNOWN_TYPE_NAME,
    base_type_name,
    to_openmetadata_type_name,
)


def test_base_type_name_strips_parameters():
    assert base_type_name("VARCHAR(50)") == "VARCHAR"
    assert base_type_name("DECIMAL(18,3)") == "DECIMAL"


def test_base_type_name_strips_nested_type_arguments():
    assert base_type_name("STRUCT(a INTEGER, b VARCHAR)") == "STRUCT"
    assert base_type_name("LIST(INTEGER)") == "LIST"


def test_base_type_name_passes_through_bare_types():
    assert base_type_name("BIGINT") == "BIGINT"


def test_to_openmetadata_type_name_known_type():
    assert to_openmetadata_type_name("VARCHAR(255)") == "VARCHAR"
    assert to_openmetadata_type_name("BIGINT") == "BIGINT"


def test_to_openmetadata_type_name_unknown_type_falls_back():
    # STRUCT/LIST/MAP are not mapped yet -- see README "Known gaps".
    assert to_openmetadata_type_name("STRUCT(a INTEGER)") == UNKNOWN_TYPE_NAME
    assert to_openmetadata_type_name("MAP(VARCHAR, INTEGER)") == UNKNOWN_TYPE_NAME
