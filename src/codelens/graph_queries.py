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
        with self.client.driver.session(database=self.client.database) as session:
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

    def _entities(self, query: str, **parameters) -> List[CodeEntity]:
        with self.client.driver.session(database=self.client.database) as session:
            return [self._to_entity(record) for record in session.run(query, **parameters)]

    def _entity(self, query: str, **parameters) -> Optional[CodeEntity]:
        with self.client.driver.session(database=self.client.database) as session:
            record = session.run(query, **parameters).single()
            return self._to_entity(record) if record else None

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
