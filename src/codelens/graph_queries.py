"""Read-only queries over the CodeLens Neo4j graph."""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .neo4j_client import Neo4jClient


_ENTITY_FIELDS = (
    "entity.id AS id, "
    "CASE "
    "WHEN entity:Function THEN 'Function' "
    "WHEN entity:Method THEN 'Method' "
    "WHEN entity:Class THEN 'Class' "
    "END AS kind, "
    "entity.name AS name, entity.file_path AS file_path, "
    "entity.start_line AS start_line, entity.end_line AS end_line"
)

_CALLERS_QUERY = (
    "MATCH (entity {id: $symbol_id})<-[:CALLS]-(caller) "
    "WHERE caller:Function OR caller:Method "
    "WITH caller AS entity "
    f"RETURN {_ENTITY_FIELDS} "
    "ORDER BY file_path, start_line, id"
)

_CALLEES_QUERY = (
    "MATCH (entity {id: $symbol_id})-[:CALLS]->(callee) "
    "WHERE callee:Function OR callee:Method "
    "WITH callee AS entity "
    f"RETURN {_ENTITY_FIELDS} "
    "ORDER BY file_path, start_line, id"
)

_SUBCLASSES_QUERY = (
    "MATCH (entity:Class {id: $class_id})<-[:EXTENDS]-(child:Class) "
    "WITH child AS entity "
    f"RETURN {_ENTITY_FIELDS} "
    "ORDER BY file_path, start_line, id"
)

_SUBJECT_QUERY = (
    "MATCH (entity {id: $symbol_id}) "
    "WHERE entity:Function OR entity:Method OR entity:Class "
    f"RETURN {_ENTITY_FIELDS}"
)

_FILES_IMPORTING_MODULE_QUERY = (
    "MATCH (file:File {repository_id: $repository_id})-[:IMPORTS]->"
    "(module:Module {name: $module_name}) "
    "RETURN file.id AS id, file.file_path AS file_path, file.name AS name "
    "ORDER BY file_path, id"
)

_FILES_IMPORTING_SYMBOL_MODULE_QUERY = (
    "MATCH (symbol {id: $symbol_id}) "
    "WHERE symbol:Function OR symbol:Method OR symbol:Class "
    "MATCH (file:File) "
    "WHERE file.repository_id = split(symbol.id, ':')[0] "
    "AND file.file_path = symbol.file_path "
    "MATCH (file)-[:IMPORTS]->(module:Module) "
    "RETURN file.repository_id AS repository_id, "
    "module.name AS module_name"
)

_RELATIONSHIPS_QUERY = (
    "MATCH (source)-[relationship]->(target) "
    "WHERE source.repository_id = $repository_id "
    "AND target.repository_id = $repository_id "
    "AND NOT source:Repository "
    "AND NOT target:Repository "
    "RETURN "
    "source.id AS source_id, "
    "source.name AS source_name, "
    "labels(source)[0] AS source_kind, "
    "type(relationship) AS relationship, "
    "target.id AS target_id, "
    "target.name AS target_name, "
    "labels(target)[0] AS target_kind "
    "ORDER BY source_id, relationship, target_id"
)

# _FILES_IMPORTING_SYMBOL_MODULE_QUERY = (
#     "MATCH (symbol {id: $symbol_id}) "
#     "WHERE symbol:Function OR symbol:Method OR symbol:Class "
#     "MATCH (file:File) "
#     "WHERE file.id = symbol.file_id "
#     "MATCH (file)-[:IMPORTS]->(module:Module) "
#     "RETURN file.repository_id AS repository_id, "
#     "module.name AS module_name"
# )

@dataclass(frozen=True)
class GraphRelationship:
    source_id: str
    source_name: str
    source_kind: str
    relationship: str
    target_id: str
    target_name: str
    target_kind: str

@dataclass(frozen=True)
class CodeEntity:
    id: str
    kind: str
    name: str
    file_path: str
    start_line: int
    end_line: Optional[int]


@dataclass(frozen=True)
class FileRef:
    id: str
    file_path: str
    name: str


@dataclass(frozen=True)
class ImpactResult:
    subject: Optional[CodeEntity]
    callers: Tuple[CodeEntity, ...]
    callees: Tuple[CodeEntity, ...]
    subclasses: Tuple[CodeEntity, ...]


class GraphQueryService:
    """Read typed CodeLens graph context from Neo4j."""

    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    def callers(self, symbol_id: str) -> List[CodeEntity]:
        return self._entities(_CALLERS_QUERY, symbol_id=symbol_id)

    def callees(self, symbol_id: str) -> List[CodeEntity]:
        return self._entities(_CALLEES_QUERY, symbol_id=symbol_id)

    def subclasses(self, class_id: str) -> List[CodeEntity]:
        return self._entities(_SUBCLASSES_QUERY, class_id=class_id)

    def impact(self, symbol_id: str) -> ImpactResult:
        subject = self._entity(_SUBJECT_QUERY, symbol_id=symbol_id)

        return ImpactResult(
            subject=subject,
            callers=tuple(self.callers(symbol_id)),
            callees=tuple(self.callees(symbol_id)),
            subclasses=tuple(self.subclasses(symbol_id)),
        )

    def files_importing_module(
        self,
        repository_id: str,
        module_name: str,
    ) -> List[FileRef]:
        with self.client.driver.session(
            database=self.client.database
        ) as session:
            records = session.run(
                _FILES_IMPORTING_MODULE_QUERY,
                repository_id=repository_id,
                module_name=module_name,
            )

            return [
                FileRef(
                    id=record["id"],
                    file_path=record["file_path"],
                    name=record["name"],
                )
                for record in records
            ]

    def files_importing_symbol_module(
        self,
        symbol_id: str,
    ) -> List[FileRef]:
        """Return files importing the module containing a symbol."""

        with self.client.driver.session(
            database=self.client.database
        ) as session:
            record = session.run(
                _FILES_IMPORTING_SYMBOL_MODULE_QUERY,
                symbol_id=symbol_id,
            ).single()

        if record is None:
            return []

        return self.files_importing_module(
            record["repository_id"],
            record["module_name"],
        )

    def _entities(
        self,
        query: str,
        **parameters,
    ) -> List[CodeEntity]:
        with self.client.driver.session(
            database=self.client.database
        ) as session:
            records = session.run(query, **parameters)
            return [self._to_entity(record) for record in records]

    def _entity(
        self,
        query: str,
        **parameters,
    ) -> Optional[CodeEntity]:
        with self.client.driver.session(
            database=self.client.database
        ) as session:
            record = session.run(query, **parameters).single()

        if record is None:
            return None

        return self._to_entity(record)

    @staticmethod
    def _to_entity(record) -> CodeEntity:
        return CodeEntity(
            id=record["id"],
            kind=record["kind"],
            name=record["name"],
            file_path=record["file_path"],
            start_line=record["start_line"],
            end_line=record["end_line"],
        )

    def relationships(
        self,
        repository_id: str,
        ) -> List[GraphRelationship]:
        """Return all code-structure relationships for a repository."""

        with self.client.driver.session(
            database=self.client.database
        ) as session:
            records = session.run(
                _RELATIONSHIPS_QUERY,
                repository_id=repository_id,
            )

            return [
                GraphRelationship(
                    source_id=record["source_id"],
                    source_name=record["source_name"],
                    source_kind=record["source_kind"],
                    relationship=record["relationship"],
                    target_id=record["target_id"],
                    target_name=record["target_name"],
                    target_kind=record["target_kind"],
                )
                for record in records
            ]
