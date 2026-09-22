import yaml

from openmetadata_ducklake_connector.openlineage_config import (
    OpenLineageKafkaConfig,
    openlineage_yaml,
    write_openlineage_yaml,
)


def test_openlineage_yaml_shape():
    config = OpenLineageKafkaConfig(bootstrap_servers="kafka:9092")
    rendered = openlineage_yaml(config)

    assert rendered["transport"]["type"] == "kafka"
    assert rendered["transport"]["topic"] == "ori-openlineage"
    assert rendered["transport"]["config"]["bootstrap.servers"] == "kafka:9092"
    assert rendered["transport"]["messageKey"] == "ori-dbt"


def test_write_openlineage_yaml_round_trips(tmp_path):
    config = OpenLineageKafkaConfig(
        bootstrap_servers="kafka-1:9092,kafka-2:9092",
        topic="custom-topic",
        message_key="custom-key",
    )
    out = tmp_path / "openlineage.yml"
    write_openlineage_yaml(config, out)

    loaded = yaml.safe_load(out.read_text())
    assert loaded["transport"]["topic"] == "custom-topic"
    assert (
        loaded["transport"]["config"]["bootstrap.servers"]
        == "kafka-1:9092,kafka-2:9092"
    )
    assert loaded["transport"]["messageKey"] == "custom-key"
