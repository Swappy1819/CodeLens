"""Neo4j graph ingestion for analyzed CodeLens repositories."""

from pathlib import Path
from typing import Iterable

from .analyzer import FileAnalysis, Symbol
from .neo4j_client import Neo4jClient


CONSTRAINT_QUERIES = (
    "CREATE CONSTRAINT repository_id_unique IF NOT EXISTS "
    "FOR (node:Repository) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT file_id_unique IF NOT EXISTS "
    "FOR (node:File) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT class_id_unique IF NOT EXISTS "
    "FOR (node:Class) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT function_id_unique IF NOT EXISTS "
    "FOR (node:Function) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT method_id_unique IF NOT EXISTS "
    "FOR (node:Method) REQUIRE node.id IS UNIQUE",
    "CREATE CONSTRAINT module_id_unique IF NOT EXISTS "
    "FOR (node:Module) REQUIRE node.id IS UNIQUE",
)


class GraphBuilder:
    """Persist AST analysis results using the CodeLens graph schema."""

    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def ensure_schema(self) -> None:
        """Create uniqueness constraints required by the graph model."""
        with self.client.driver.session(database=self.client.database) as session:
            for query in CONSTRAINT_QUERIES:
                session.run(query).consume()

    def ingest(self, repository_name: str, analyses: Iterable[FileAnalysis]) -> None:
        """Persist analysis results for a repository without creating duplicates."""
        self.ensure_schema()
        repository_id = repository_name

        with self.client.driver.session(database=self.client.database) as session:
            for analysis in analyses:
                self._merge_file(session, repository_id, repository_name, analysis)
                self._merge_symbols(session, repository_id, analysis)

    def _merge_file(
        self,
        session,
        repository_id: str,
        repository_name: str,
        analysis: FileAnalysis,
    ) -> None:
        file_path = str(analysis.file_path)
        session.run(
            "MERGE (repository:Repository {id: $repository_id}) "
            "SET repository.name = $repository_name, "
            "repository.repository_id = $repository_id "
            "MERGE (file:File {id: $file_id}) "
            "SET file.name = $file_name, file.file_path = $file_path, "
            "file.repository_id = $repository_id "
            "MERGE (repository)-[:CONTAINS]->(file)",
            repository_id=repository_id,
            repository_name=repository_name,
            file_id=self._file_id(repository_id, analysis.file_path),
            file_name=analysis.file_path.name,
            file_path=file_path,
        ).consume()

    def _merge_symbols(
        self,
        session,
        repository_id: str,
        analysis: FileAnalysis,
    ) -> None:
        for symbol in analysis.symbols:
            if symbol.symbol_type == "class":
                self._merge_class(session, repository_id, symbol)

        for symbol in analysis.symbols:
            if symbol.symbol_type == "function":
                self._merge_function(session, repository_id, symbol)
            elif symbol.symbol_type == "method":
                self._merge_method(session, repository_id, symbol)
            elif symbol.symbol_type in ("import", "from_import"):
                self._merge_import(session, repository_id, symbol)

    def _merge_class(self, session, repository_id: str, symbol: Symbol) -> None:
        session.run(
            "MATCH (file:File {id: $file_id}) "
            "MERGE (class:Class {id: $class_id}) "
            "SET class.name = $name, class.file_path = $file_path, "
            "class.start_line = $start_line, class.end_line = $end_line, "
            "class.repository_id = $repository_id "
            "MERGE (file)-[:CONTAINS]->(class)",
            **self._symbol_parameters(repository_id, symbol, "class"),
        ).consume()

    def _merge_function(self, session, repository_id: str, symbol: Symbol) -> None:
        session.run(
            "MATCH (file:File {id: $file_id}) "
            "MERGE (function:Function {id: $function_id}) "
            "SET function.name = $name, function.file_path = $file_path, "
            "function.start_line = $start_line, function.end_line = $end_line, "
            "function.repository_id = $repository_id "
            "MERGE (file)-[:CONTAINS]->(function)",
            **self._symbol_parameters(repository_id, symbol, "function"),
        ).consume()

    def _merge_method(self, session, repository_id: str, symbol: Symbol) -> None:
        if symbol.parent_name is None:
            return

        parameters = self._symbol_parameters(repository_id, symbol, "method")
        parameters["class_id"] = self._class_id(
            repository_id,
            symbol.file_path,
            symbol.parent_name,
        )
        session.run(
            "MATCH (class:Class {id: $class_id}) "
            "MERGE (method:Method {id: $method_id}) "
            "SET method.name = $name, method.file_path = $file_path, "
            "method.start_line = $start_line, method.end_line = $end_line, "
            "method.repository_id = $repository_id "
            "MERGE (class)-[:CONTAINS]->(method)",
            **parameters,
        ).consume()

    def _merge_import(self, session, repository_id: str, symbol: Symbol) -> None:
        if symbol.module is None:
            return

        session.run(
            "MATCH (file:File {id: $file_id}) "
            "MERGE (module:Module {id: $module_id}) "
            "SET module.name = $module_name "
            "MERGE (file)-[:IMPORTS]->(module)",
            file_id=self._file_id(repository_id, symbol.file_path),
            module_id=symbol.module,
            module_name=symbol.module,
        ).consume()

    def _symbol_parameters(
        self,
        repository_id: str,
        symbol: Symbol,
        entity_type: str,
    ) -> dict:
        file_path = str(symbol.file_path)
        parameters = {
            "repository_id": repository_id,
            "file_id": self._file_id(repository_id, symbol.file_path),
            "file_path": file_path,
            "name": symbol.name,
            "start_line": symbol.start_line,
            "end_line": symbol.end_line,
        }
        if entity_type == "class":
            parameters["class_id"] = self._class_id(
                repository_id, symbol.file_path, symbol.name
            )
        elif entity_type == "function":
            parameters["function_id"] = self._function_id(repository_id, symbol)
        elif entity_type == "method":
            parameters["method_id"] = self._method_id(repository_id, symbol)
        return parameters

    @staticmethod
    def _file_id(repository_id: str, file_path: Path) -> str:
        return f"{repository_id}:{file_path}"

    @staticmethod
    def _class_id(repository_id: str, file_path: Path, name: str) -> str:
        return f"{repository_id}:{file_path}:{name}"

    def _function_id(self, repository_id: str, symbol: Symbol) -> str:
        return (
            f"{repository_id}:{symbol.file_path}:{symbol.name}:{symbol.start_line}"
        )

    def _method_id(self, repository_id: str, symbol: Symbol) -> str:
        return (
            f"{repository_id}:{symbol.file_path}:{symbol.parent_name}:"
            f"{symbol.name}:{symbol.start_line}"
        )
