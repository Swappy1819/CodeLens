import os
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from codelens.analyzer import CallSite, ClassBase, FileAnalysis, Symbol, analyze_repository
from codelens.graph_builder import CONSTRAINT_QUERIES, GraphBuilder
from codelens.graph_queries import GraphQueryService
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


def test_resolves_repository_local_imports_and_aliases() -> None:
    caller_path = Path("caller.py")
    payments_path = Path("payments.py")
    analyses = [
        FileAnalysis(
            file_path=caller_path,
            symbols=[
                Symbol("caller", "function", caller_path, 4, 7),
                Symbol(
                    "process_payment",
                    "from_import",
                    caller_path,
                    1,
                    1,
                    module="payments",
                    imported_name="process_payment",
                ),
                Symbol(
                    "pay",
                    "from_import",
                    caller_path,
                    2,
                    2,
                    module="payments",
                    imported_name="process_payment",
                ),
                Symbol(
                    "p",
                    "import",
                    caller_path,
                    3,
                    3,
                    module="payments",
                    imported_name="payments",
                ),
            ],
            calls=[
                CallSite(
                    "function",
                    "caller",
                    caller_path,
                    4,
                    None,
                    "process_payment",
                    None,
                    5,
                    4,
                ),
                CallSite(
                    "function", "caller", caller_path, 4, None, "pay", None, 6, 4
                ),
                CallSite(
                    "function",
                    "caller",
                    caller_path,
                    4,
                    None,
                    "process_payment",
                    "p",
                    7,
                    4,
                ),
            ],
        ),
        FileAnalysis(
            file_path=payments_path,
            symbols=[Symbol("process_payment", "function", payments_path, 1, 2)],
        ),
    ]
    driver = FakeDriver()
    builder = GraphBuilder(SimpleNamespace(driver=driver, database="neo4j"))

    builder.ingest("sample-repository", analyses)

    _, ingestion_session = driver.sessions[1]
    call_parameters = [
        parameters
        for query, parameters in ingestion_session.calls
        if "[:CALLS" in query
    ]
    assert len(call_parameters) == 3
    assert {parameters["callee_id"] for parameters in call_parameters} == {
        "sample-repository:payments.py:process_payment:1"
    }


def test_resolves_straightforward_relative_imports() -> None:
    caller_path = Path("package/caller.py")
    payments_path = Path("package/payments.py")
    analyses = [
        FileAnalysis(
            file_path=caller_path,
            symbols=[
                Symbol("caller", "function", caller_path, 3, 4),
                Symbol(
                    "process_payment",
                    "from_import",
                    caller_path,
                    1,
                    1,
                    module="payments",
                    imported_name="process_payment",
                    relative_import_level=1,
                ),
            ],
            calls=[
                CallSite(
                    "function",
                    "caller",
                    caller_path,
                    3,
                    None,
                    "process_payment",
                    None,
                    4,
                    4,
                )
            ],
        ),
        FileAnalysis(
            file_path=payments_path,
            symbols=[Symbol("process_payment", "function", payments_path, 1, 2)],
        ),
    ]
    driver = FakeDriver()
    builder = GraphBuilder(SimpleNamespace(driver=driver, database="neo4j"))

    builder.ingest("sample-repository", analyses)

    _, ingestion_session = driver.sessions[1]
    call_parameters = [
        parameters
        for query, parameters in ingestion_session.calls
        if "[:CALLS" in query
    ]
    assert call_parameters[0]["callee_id"] == (
        "sample-repository:package/payments.py:process_payment:1"
    )


def test_resolves_same_file_and_imported_class_bases() -> None:
    models_path = Path("models.py")
    bases_path = Path("bases.py")
    analyses = [
        FileAnalysis(
            file_path=models_path,
            symbols=[
                Symbol("Base", "class", models_path, 1, 2),
                Symbol("Child", "class", models_path, 4, 5),
                Symbol("ImportedChild", "class", models_path, 7, 8),
                Symbol("ModuleChild", "class", models_path, 10, 11),
                Symbol(
                    "ExternalBase",
                    "from_import",
                    models_path,
                    1,
                    1,
                    module="bases",
                    imported_name="ExternalBase",
                ),
                Symbol(
                    "base_module",
                    "import",
                    models_path,
                    2,
                    2,
                    module="bases",
                    imported_name="bases",
                ),
            ],
            bases=[
                ClassBase("Child", models_path, 4, "Base", None, 4, 12),
                ClassBase(
                    "ImportedChild", models_path, 7, "ExternalBase", None, 7, 20
                ),
                ClassBase(
                    "ModuleChild", models_path, 10, "ExternalBase", "base_module", 10, 18
                ),
            ],
        ),
        FileAnalysis(
            file_path=bases_path,
            symbols=[Symbol("ExternalBase", "class", bases_path, 1, 2)],
        ),
    ]
    driver = FakeDriver()
    builder = GraphBuilder(SimpleNamespace(driver=driver, database="neo4j"))

    builder.ingest("sample-repository", analyses)

    _, ingestion_session = driver.sessions[1]
    relationship_parameters = [
        parameters
        for query, parameters in ingestion_session.calls
        if "[:EXTENDS" in query
    ]
    assert len(relationship_parameters) == 3
    assert {parameters["base_id"] for parameters in relationship_parameters} == {
        "sample-repository:models.py:Base",
        "sample-repository:bases.py:ExternalBase",
    }
    assert all("ExternalBase" not in query for query, _ in ingestion_session.calls)


def test_resolves_straightforward_relative_class_bases() -> None:
    child_path = Path("package/child.py")
    base_path = Path("package/bases.py")
    analyses = [
        FileAnalysis(
            file_path=child_path,
            symbols=[
                Symbol("Child", "class", child_path, 3, 4),
                Symbol(
                    "Base",
                    "from_import",
                    child_path,
                    1,
                    1,
                    module="bases",
                    imported_name="Base",
                    relative_import_level=1,
                ),
            ],
            bases=[ClassBase("Child", child_path, 3, "Base", None, 3, 12)],
        ),
        FileAnalysis(
            file_path=base_path,
            symbols=[Symbol("Base", "class", base_path, 1, 2)],
        ),
    ]
    driver = FakeDriver()
    builder = GraphBuilder(SimpleNamespace(driver=driver, database="neo4j"))

    builder.ingest("sample-repository", analyses)

    _, ingestion_session = driver.sessions[1]
    relationship_parameters = [
        parameters
        for query, parameters in ingestion_session.calls
        if "[:EXTENDS" in query
    ]
    assert relationship_parameters == [
        {
            "child_id": "sample-repository:package/child.py:Child",
            "base_id": "sample-repository:package/bases.py:Base",
        }
    ]


def test_skips_unresolved_class_bases() -> None:
    file_path = Path("models.py")
    analysis = FileAnalysis(
        file_path=file_path,
        symbols=[Symbol("Child", "class", file_path, 1, 2)],
        bases=[ClassBase("Child", file_path, 1, "ExternalBase", None, 1, 12)],
    )
    driver = FakeDriver()
    builder = GraphBuilder(SimpleNamespace(driver=driver, database="neo4j"))

    builder.ingest("sample-repository", [analysis])

    _, ingestion_session = driver.sessions[1]
    assert not any("[:EXTENDS" in query for query, _ in ingestion_session.calls)


def test_skips_ambiguous_class_bases() -> None:
    child_path = Path("child.py")
    module_path = Path("bases.py")
    package_path = Path("bases/__init__.py")
    analyses = [
        FileAnalysis(
            file_path=child_path,
            symbols=[
                Symbol("Child", "class", child_path, 2, 3),
                Symbol(
                    "bases",
                    "import",
                    child_path,
                    1,
                    1,
                    module="bases",
                    imported_name="bases",
                ),
            ],
            bases=[ClassBase("Child", child_path, 2, "Base", "bases", 2, 12)],
        ),
        FileAnalysis(
            file_path=module_path,
            symbols=[Symbol("Base", "class", module_path, 1, 2)],
        ),
        FileAnalysis(
            file_path=package_path,
            symbols=[Symbol("Base", "class", package_path, 1, 2)],
        ),
    ]
    driver = FakeDriver()
    builder = GraphBuilder(SimpleNamespace(driver=driver, database="neo4j"))

    builder.ingest("sample-repository", analyses)

    _, ingestion_session = driver.sessions[1]
    assert not any("[:EXTENDS" in query for query, _ in ingestion_session.calls)


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
    payments = tmp_path / "payments.py"
    bases = tmp_path / "bases.py"
    payments.write_text("def process_payment():\n    pass\n")
    bases.write_text("class PaymentBase:\n    pass\n")
    source.write_text(
        f"import {module_name}\n"
        f"from {module_name} import helper\n\n"
        "from payments import process_payment as pay\n\n"
        "from bases import PaymentBase as Base\n\n"
        "class Example(Base):\n"
        "    def method(self):\n"
        "        pass\n\n"
        "    def caller(self):\n"
        "        self.method()\n\n"
        "def helper():\n"
        "    pass\n\n"
        "def function():\n"
        "    helper()\n"
        "    pay()\n"
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
                "OPTIONAL MATCH (child)-[extends:EXTENDS]->(base) "
                "WHERE child.repository_id = $repository_id "
                "OPTIONAL MATCH (caller)-[call:CALLS]->(callee) "
                "WHERE caller.repository_id = $repository_id "
                "RETURN count(DISTINCT repository_file) AS repository_files, "
                "count(DISTINCT file_class) AS file_classes, "
                "count(DISTINCT class_method) AS class_methods, "
                "count(DISTINCT file_function) AS file_functions, "
                "count(DISTINCT file_module) AS file_modules, "
                "count(DISTINCT extends) AS extends, "
                "count(DISTINCT call) AS calls",
                repository_id=repository_id,
            ).single()

        assert dict(record) == {
            "repository_files": 3,
            "file_classes": 2,
            "class_methods": 2,
            "file_functions": 3,
            "file_modules": 3,
            "extends": 1,
            "calls": 3,
        }

        queries = GraphQueryService(client)
        function_id = f"{repository_id}:example.py:function:18"
        assert [entity.name for entity in queries.callers(function_id)] == []
        assert [entity.name for entity in queries.callees(function_id)] == [
            "helper",
            "process_payment",
        ]
        assert [
            entity.name
            for entity in queries.subclasses(
                f"{repository_id}:bases.py:PaymentBase"
            )
        ] == ["Example"]
        assert [
            file.file_path
            for file in queries.files_importing_module(repository_id, "payments")
        ] == ["example.py"]
        assert [entity.name for entity in queries.impact(function_id).callees] == [
            "helper",
            "process_payment",
        ]
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
