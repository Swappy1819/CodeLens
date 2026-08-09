"""Small Neo4j connection wrapper for CodeLens."""

import os
from typing import Optional

from neo4j import Driver, GraphDatabase


class Neo4jClient:
    """Create and manage a Neo4j driver from environment configuration."""

    def __init__(self) -> None:
        self.uri = self._required_environment_value("NEO4J_URI")
        self.username = self._required_environment_value("NEO4J_USERNAME")
        self.password = self._required_environment_value("NEO4J_PASSWORD")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
        self.driver: Driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password),
        )

    def verify_connection(self) -> None:
        """Raise an error if the configured Neo4j database is unreachable."""
        self.driver.verify_connectivity(database=self.database)

    def close(self) -> None:
        """Close the underlying Neo4j driver."""
        self.driver.close()

    @staticmethod
    def _required_environment_value(name: str) -> str:
        value: Optional[str] = os.getenv(name)
        if not value:
            raise ValueError(f"Missing required environment variable: {name}")
        return value
