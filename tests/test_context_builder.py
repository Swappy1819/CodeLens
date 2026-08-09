from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from codelens.context_builder import ContextBuilder, ContextLimits


def entity(entity_id, name, file_path, start_line, kind="Function"):
    return SimpleNamespace(
        id=entity_id,
        kind=kind,
        name=name,
        file_path=file_path,
        start_line=start_line,
        end_line=start_line + 1,
    )


class FakeGraphQueries:
    def __init__(self, subject=None, callers=(), callees=(), subclasses=()):
        self.result = SimpleNamespace(
            subject=subject,
            callers=callers,
            callees=callees,
            subclasses=subclasses,
        )
        self.requested_ids = []

    def impact(self, symbol_id):
        self.requested_ids.append(symbol_id)
        return self.result


def test_builds_context_with_separate_location_models_in_deterministic_order() -> None:
    queries = FakeGraphQueries(
        subject=entity("repo:main.py:target:3", "target", "main.py", 3),
        callers=(
            entity("repo:z.py:last:2", "last", "z.py", 2),
            entity("repo:a.py:first:4", "first", "a.py", 4),
        ),
    )

    context = ContextBuilder(queries).build("repo:main.py:target:3")

    assert queries.requested_ids == ["repo:main.py:target:3"]
    assert context.subject.location.file_path == "main.py"
    assert context.subject.location.start_line == 3
    assert [symbol.name for symbol in context.callers] == ["first", "last"]
    assert context.truncated_sections == ()


def test_returns_empty_context_for_missing_subject_and_relationships() -> None:
    context = ContextBuilder(FakeGraphQueries()).build("missing")

    assert context.subject is None
    assert context.callers == ()
    assert context.callees == ()
    assert context.subclasses == ()
    assert context.truncated_sections == ()


def test_applies_each_section_limit_and_marks_truncation() -> None:
    queries = FakeGraphQueries(
        subject=entity("repo:subject.py:target:1", "target", "subject.py", 1),
        callers=(
            entity("repo:c.py:one:1", "one", "c.py", 1),
            entity("repo:c.py:two:2", "two", "c.py", 2),
        ),
        callees=(
            entity("repo:d.py:one:1", "one", "d.py", 1),
            entity("repo:d.py:two:2", "two", "d.py", 2),
            entity("repo:d.py:three:3", "three", "d.py", 3),
        ),
        subclasses=(
            entity("repo:s.py:one", "one", "s.py", 1, "Class"),
        ),
    )

    context = ContextBuilder(queries).build(
        "repo:subject.py:target:1",
        ContextLimits(max_callers=1, max_callees=2, max_subclasses=0),
    )

    assert [symbol.name for symbol in context.callers] == ["one"]
    assert [symbol.name for symbol in context.callees] == ["one", "two"]
    assert context.subclasses == ()
    assert context.truncated_sections == ("callers", "callees", "subclasses")


def test_limit_boundaries_do_not_mark_complete_sections_as_truncated() -> None:
    queries = FakeGraphQueries(
        callers=(entity("repo:c.py:one:1", "one", "c.py", 1),),
        callees=(entity("repo:d.py:one:1", "one", "d.py", 1),),
        subclasses=(entity("repo:s.py:one", "one", "s.py", 1, "Class"),),
    )

    context = ContextBuilder(queries).build(
        "missing-subject",
        ContextLimits(max_callers=1, max_callees=1, max_subclasses=1),
    )

    assert len(context.callers) == len(context.callees) == len(context.subclasses) == 1
    assert context.truncated_sections == ()


def test_rejects_negative_context_limits() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ContextBuilder(FakeGraphQueries()).build(
            "symbol",
            ContextLimits(max_callers=-1),
        )
