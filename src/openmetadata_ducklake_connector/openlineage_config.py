"""Generates the openlineage.yml that `dbt-ol` reads, pointed at the Kafka
topic OpenMetadata's OpenLineage connector consumes from.

STATUS: sketch, not run against a live Kafka broker, `dbt-ol`, or
OpenMetadata's OpenLineage connector. See the README "OpenLineage lineage
layer" section for why this needs a message broker in the middle rather
than a plain HTTP URL, and what that means for a stack that otherwise has
no database servers to babysit.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel


class OpenLineageKafkaConfig(BaseModel):
    """What both dbt-ol (as a producer) and OpenMetadata's OpenLineage
    connector (as a consumer) need to agree on for lineage events to
    connect up. OpenMetadata's OpenLineage pipeline service currently
    consumes from Kafka, Kinesis or NATS JetStream (its `brokerConfig`) --
    there is no plain HTTP POST endpoint the way there is for e.g. Marquez.
    This sketch only covers the Kafka path; OpenMetadata's own ingestion
    workflow config on the consuming side is not included here.
    """

    bootstrap_servers: str
    topic: str = "ori-openlineage"
    namespace: str = "ori-ducklake"
    message_key: str = "ori-dbt"
    acks: str = "all"


def openlineage_yaml(config: OpenLineageKafkaConfig) -> dict:
    """The dict `dbt-ol` expects in openlineage.yml (or via the
    OPENLINEAGE_CONFIG env var). See
    https://openlineage.io/docs/client/python for the transport shape.
    """
    return {
        "transport": {
            "type": "kafka",
            "topic": config.topic,
            "config": {
                "bootstrap.servers": config.bootstrap_servers,
                "acks": config.acks,
            },
            "flush": True,
            "messageKey": config.message_key,
        }
    }


def write_openlineage_yaml(config: OpenLineageKafkaConfig, path: Path) -> None:
    path.write_text(yaml.safe_dump(openlineage_yaml(config), sort_keys=False))
