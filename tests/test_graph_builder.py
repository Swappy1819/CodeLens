import os
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from codelens.analyzer import CallSite, FileAnalysis, Symbol, analyze_repository
from codelens.graph_builder import CONSTRAINT_QUERIES, GraphBuilder
from codelens.neo4j_client import Neo4jClient


class FakeResult:
    def consume(self):
        return None


class FakeSession:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def run(self, query, **parameters):
        self.calls.append((query, parameters))
        return FakeResult()


class FakeDriver:
    def __init__(self):
        self.sessions = []

    def session(self, **options):
        session = FakeSession()
        self.sessions.append((options, session))
        return session


def test_creates_uniqueness_constraints() -> None:
    driver = FakeDriver()
    builder = GraphBuilder(SimpleNamespace(driver=driver, database="neo4j"))

    builder.ensure_schema()

    options, session = driver.sessions[0]
    assert options == {"database": "neo4j"}
    assert [query for query, _ in session.calls] == list(CONSTRAINT_QUERIES)


def test_ingests_graph_entities_with_stable_ids_and_parameters() -> None:
    analysis = FileAnalysis(
        file_path=Path("package/example.py"),
        symbols=[
            Symbol("Example", "class", Path("package/example.py"), 3, 7),
            Symbol(
                "run",
                "method",
                Path("package/example.py"),
                4,
                7,
                parent_name="Example",
            ),
            Symbol("helper", "function", Path("package/example.py"), 10, 11),
            Symbol("pathlib", "import", Path("package/example.py"), 1, 1, module="pathlib"),
        ],
    )
    driver = FakeDriver()
    builder = GraphBuilder(SimpleNamespace(driver=driver, database="neo4j"))

    builder.ingest("sample-repository", [analysis])

    _, ingestion_session = driver.sessions[1]
    queries = [query for query, _ in ingestion_session.calls]
    parameters = [parameters for _, parameters in ingestion_session.calls]

    assert any("MERGE (repository:Repository" in query for query in queries)
    assert any("MERGE (class:Class" in query for query in queries)
    assert any("MERGE (function:Function" in query for query in queries)
    assert any("MERGE (method:Method" in query for query in queries)
    assert any("MERGE (module:Module" in query for query in queries)
    assert all("Example" not in query for query in queries)
    assert {
        "sample-repository:package/example.py:Example",
        "sample-repository:package/example.py:helper:10",
        "sample-repository:package/example.py:Example:run:4",
    }.issubset({value for parameter in parameters for value in parameter.values()})


def test_ingests_syntax_error_files_as_files_without_symbols() -> None:
    driver = FakeDriver()
    builder = GraphBuilder(SimpleNamespace(driver=driver, database="neo4j"))
    analysis = FileAnalysis(Path("broken.py"), [], syntax_error="invalid syntax")

    builder.ingest("sample-repository", [analysis])

    _, ingestion_session = driver.sessions[1]
    assert len(ingestion_session.calls) == 1
    assert "MERGE (file:File" in ingestion_session.calls[0][0]


def test_resolves_unqualified_function_calls() -> None:
    file_path = Path("calls.py")
    analysis = FileAnalysis(
        file_path=file_path,
        symbols=[
            Symbol("helper", "function", file_path, 1, 2),
            Symbol("caller", "function", file_path, 4, 5),
        ],
        calls=[
            CallSite(
                "function", "caller", file_path, 4, None, "helper", None, 5, 4
            )
        ],
    )
    driver = FakeDriver()
    builder = GraphBuilder(SimpleNamespace(driver=driver, database="neo4j"))

    builder.ingest("sample-repository", [analysis])

    _, ingestion_session = driver.sessions[1]
    query, parameters = ingestion_session.calls[-1]
    assert "MERGE (caller)-[:CALLS" in query
    assert "helper" not in query
    assert parameters == {
        "caller_id": "sample-repository:calls.py:caller:4",
        "callee_id": "sample-repository:calls.py:helper:1",
        "file_path": "calls.py",
        "start_line": 5,
        "start_column": 4,
    }


def test_resolves_self_method_calls() -> None:
    file_path = Path("calls.py")
    analysis = FileAnalysis(
        file_path=file_path,
        symbols=[
            Symbol("run", "method", file_path, 2, 3, parent_name="Service"),
            Symbol("prepare", "method", file_path, 5, 6, parent_name="Service"),
        ],
        calls=[
            CallSite(
                "method", "run", file_path, 2, "Service", "prepare", "self", 3, 8
            )
        ],
    )
    driver = FakeDriver()
    builder = GraphBuilder(SimpleNamespace(driver=driver, database="neo4j"))

    builder.ingest("sample-repository", [analysis])

    _, ingestion_session = driver.sessions[1]
    _, parameters = ingestion_session.calls[-1]
    assert parameters["caller_id"] == "sample-repository:calls.py:Service:run:2"
    assert parameters["callee_id"] == "sample-repository:calls.py:Service:prepare:5"


def test_skips_ambiguous_and_unresolved_call_targets() -> None:
    file_path = Path("calls.py")
    analysis = FileAnalysis(
        file_path=file_path,
        symbols=[
            Symbol("caller", "function", file_path, 1, 4),
            Symbol("helper", "function", file_path, 6, 7),
            Symbol("helper", "function", file_path, 9, 10),
        ],
        calls=[
            CallSite("function", "caller", file_path, 1, None, "helper", None, 2, 4),
            CallSite("function", "caller", file_path, 1, None, "missing", None, 3, 4),
            CallSite("function", "caller", file_path, 1, None, "run", "service", 4, 4),
        ],
    )
    driver = FakeDriver()
    builder = GraphBuilder(SimpleNamespace(driver=driver, database="neo4j"))

    builder.ingest("sample-repository", [analysis])

    _, ingestion_session = driver.sessions[1]
    assert not any("[:CALLS" in query for query, _ in ingestion_session.calls)


@pytest.mark.skipif(
    not all(
        os.getenv(name) for name in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")
    ),
    reason="Neo4j connection environment variables are not configured",
)
def test_ingests_graph_into_live_neo4j(tmp_path: Path) -> None:
    repository_id = f"codelens-integration-{uuid4()}"
    module_name = f"codelens_test_module_{uuid4().hex}"
    source = tmp_path / "example.py"
    source.write_text(
        f"import {module_name}\n"
        f"from {module_name} import helper\n\n"
        "class Example:\n"
        "    def method(self):\n"
        "        pass\n\n"
        "    def caller(self):\n"
        "        self.method()\n\n"
        "def helper():\n"
        "    pass\n\n"
        "def function():\n"
        "    helper()\n"
    )
    client = Neo4jClient()
    builder = GraphBuilder(client)

    try:
        builder.ingest(repository_id, analyze_repository(tmp_path))
        with client.driver.session(database=client.database) as session:
            record = session.run(
                "MATCH (repository:Repository {id: $repository_id}) "
                "OPTIONAL MATCH (repository)-[repository_file:CONTAINS]->(file:File) "
                "OPTIONAL MATCH (file)-[file_class:CONTAINS]->(class:Class) "
                "OPTIONAL MATCH (class)-[class_method:CONTAINS]->(method:Method) "
                "OPTIONAL MATCH (file)-[file_function:CONTAINS]->(function:Function) "
                "OPTIONAL MATCH (file)-[file_module:IMPORTS]->(module:Module) "
                "OPTIONAL MATCH (caller)-[call:CALLS]->(callee) "
                "WHERE caller.repository_id = $repository_id "
                "RETURN count(DISTINCT repository_file) AS repository_files, "
                "count(DISTINCT file_class) AS file_classes, "
                "count(DISTINCT class_method) AS class_methods, "
                "count(DISTINCT file_function) AS file_functions, "
                "count(DISTINCT file_module) AS file_modules, "
                "count(DISTINCT call) AS calls",
                repository_id=repository_id,
            ).single()

        assert dict(record) == {
            "repository_files": 1,
            "file_classes": 1,
            "class_methods": 2,
            "file_functions": 2,
            "file_modules": 1,
            "calls": 2,
        }
    finally:
        with client.driver.session(database=client.database) as session:
            session.run(
                "MATCH (node {repository_id: $repository_id}) DETACH DELETE node",
                repository_id=repository_id,
            ).consume()
            session.run(
                "MATCH (module:Module {id: $module_id}) DETACH DELETE module",
                module_id=module_name,
            ).consume()
        client.close()
