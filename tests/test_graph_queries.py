from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from codelens.graph_queries import GraphQueryService


def entity_record(entity_id, name, file_path="code.py", start_line=1, kind="Function"):
    return {
        "id": entity_id,
        "kind": kind,
        "name": name,
        "file_path": file_path,
        "start_line": start_line,
        "end_line": start_line + 1,
    }


class FakeResult:
    def __init__(self, records):
        self.records = records

    def __iter__(self):
        return iter(self.records)

    def single(self):
        return self.records[0] if self.records else None


class FakeSession:
    def __init__(self, driver):
        self.driver = driver

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def run(self, query, **parameters):
        self.driver.calls.append((query, parameters))
        return FakeResult(self.driver.responses.pop(0))


class FakeDriver:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def session(self, **options):
        assert options == {"database": "neo4j"}
        return FakeSession(self)


def service_with_responses(*responses):
    driver = FakeDriver(responses)
    return GraphQueryService(SimpleNamespace(driver=driver, database="neo4j")), driver


def test_callers_returns_typed_entities_with_parameterized_ordered_query() -> None:
    service, driver = service_with_responses(
        [
            entity_record("repo:a.py:caller:1", "caller", "a.py", 1),
            entity_record("repo:b.py:caller:1", "caller", "b.py", 1),
        ]
    )

    callers = service.callers("repo:target:2")

    assert [caller.file_path for caller in callers] == ["a.py", "b.py"]
    query, parameters = driver.calls[0]
    assert "repo:target:2" not in query
    assert parameters == {"symbol_id": "repo:target:2"}
    assert "ORDER BY file_path, start_line, id" in query


def test_callees_returns_empty_list_for_missing_target() -> None:
    service, _ = service_with_responses([])

    assert service.callees("missing") == []


def test_subclasses_returns_typed_class_entities() -> None:
    service, driver = service_with_responses(
        [entity_record("repo:child.py:Child", "Child", "child.py", 3, "Class")]
    )

    subclasses = service.subclasses("repo:base.py:Base")

    assert subclasses[0].kind == "Class"
    query, parameters = driver.calls[0]
    assert "[:EXTENDS]" in query
    assert parameters == {"class_id": "repo:base.py:Base"}


def test_impact_composes_direct_typed_neighbors() -> None:
    service, _ = service_with_responses(
        [entity_record("repo:base.py:Base", "Base", "base.py", 1, "Class")],
        [entity_record("repo:caller.py:run:2", "run", "caller.py", 2)],
        [entity_record("repo:callee.py:work:4", "work", "callee.py", 4)],
        [entity_record("repo:child.py:Child", "Child", "child.py", 3, "Class")],
    )

    result = service.impact("repo:base.py:Base")

    assert result.subject.name == "Base"
    assert [entity.name for entity in result.callers] == ["run"]
    assert [entity.name for entity in result.callees] == ["work"]
    assert [entity.name for entity in result.subclasses] == ["Child"]


def test_impact_returns_empty_context_for_missing_symbol() -> None:
    service, _ = service_with_responses([], [], [], [])

    result = service.impact("missing")

    assert result.subject is None
    assert result.callers == ()
    assert result.callees == ()
    assert result.subclasses == ()


def test_files_importing_module_returns_ordered_file_refs() -> None:
    service, driver = service_with_responses(
        [
            {"id": "repo:a.py", "file_path": "a.py", "name": "a.py"},
            {"id": "repo:b.py", "file_path": "b.py", "name": "b.py"},
        ]
    )

    files = service.files_importing_module("repo", "payments")

    assert [file.file_path for file in files] == ["a.py", "b.py"]
    query, parameters = driver.calls[0]
    assert "payments" not in query
    assert parameters == {"repository_id": "repo", "module_name": "payments"}
    assert "ORDER BY file_path, id" in query
