import os
from pathlib import Path
import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from codelens.neo4j_client import Neo4jClient


def configure_neo4j_environment(monkeypatch, database=None) -> None:
    monkeypatch.setenv("NEO4J_URI", "neo4j://localhost:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "test-password")
    if database is not None:
        monkeypatch.setenv("NEO4J_DATABASE", database)


def test_initializes_driver_from_environment(monkeypatch) -> None:
    configure_neo4j_environment(monkeypatch, database="codelens")
    driver = Mock()

    with patch("codelens.neo4j_client.GraphDatabase.driver", return_value=driver) as create_driver:
        client = Neo4jClient()

    create_driver.assert_called_once_with(
        "neo4j://localhost:7687",
        auth=("neo4j", "test-password"),
    )
    assert client.database == "codelens"


def test_defaults_database_to_neo4j(monkeypatch) -> None:
    configure_neo4j_environment(monkeypatch)
    monkeypatch.delenv("NEO4J_DATABASE", raising=False)

    with patch("codelens.neo4j_client.GraphDatabase.driver"):
        client = Neo4jClient()

    assert client.database == "neo4j"


def test_requires_connection_environment_variables(monkeypatch) -> None:
    for name in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError, match="NEO4J_URI"):
        Neo4jClient()


def test_verifies_connection_and_closes_driver(monkeypatch) -> None:
    configure_neo4j_environment(monkeypatch)
    driver = Mock()

    with patch("codelens.neo4j_client.GraphDatabase.driver", return_value=driver):
        client = Neo4jClient()

    client.verify_connection()
    client.close()

    driver.verify_connectivity.assert_called_once_with(database="neo4j")
    driver.close.assert_called_once_with()


@pytest.mark.skipif(
    not all(
        os.getenv(name) for name in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")
    ),
    reason="Neo4j connection environment variables are not configured",
)
def test_live_neo4j_connection() -> None:
    client = Neo4jClient()
    try:
        client.verify_connection()
    finally:
        client.close()
