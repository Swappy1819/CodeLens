from dataclasses import dataclass

import pytest

from codelens.context_builder import (
    ContextBuilder,
    ContextFile,
    ContextLimits,
    ContextSymbol,
    SourceLocation,
    SymbolContext,
)


@dataclass(frozen=True)
class FakeEntity:
    id: str
    kind: str
    name: str
    file_path: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class FakeFile:
    id: str
    file_path: str
    name: str


@dataclass(frozen=True)
class FakeImpact:
    subject: FakeEntity
    callers: tuple
    callees: tuple
    subclasses: tuple


class FakeGraphQueries:
    def __init__(self):
        self.impact_result = FakeImpact(
            subject=FakeEntity(
                id="repo:main.py:target:3",
                kind="Function",
                name="target",
                file_path="main.py",
                start_line=3,
                end_line=5,
            ),
            callers=(
                FakeEntity(
                    id="repo:z.py:caller:10",
                    kind="Function",
                    name="caller",
                    file_path="z.py",
                    start_line=10,
                    end_line=12,
                ),
                FakeEntity(
                    id="repo:a.py:caller:2",
                    kind="Function",
                    name="caller",
                    file_path="a.py",
                    start_line=2,
                    end_line=4,
                ),
            ),
            callees=(
                FakeEntity(
                    id="repo:b.py:helper:8",
                    kind="Function",
                    name="helper",
                    file_path="b.py",
                    start_line=8,
                    end_line=9,
                ),
            ),
            subclasses=(
                FakeEntity(
                    id="repo:c.py:Child",
                    kind="Class",
                    name="Child",
                    file_path="c.py",
                    start_line=1,
                    end_line=5,
                ),
            ),
        )

        self.importing_files = (
            FakeFile(
                id="repo:z.py",
                file_path="z.py",
                name="z",
            ),
            FakeFile(
                id="repo:a.py",
                file_path="a.py",
                name="a",
            ),
        )

    def impact(self, symbol_id):
        return self.impact_result

    def files_importing_symbol_module(self, symbol_id):
        return self.importing_files


def test_builds_context_with_separate_location_models_in_deterministic_order():
    queries = FakeGraphQueries()

    context = ContextBuilder(queries).build(
        "repo:main.py:target:3"
    )

    assert isinstance(context, SymbolContext)

    assert context.subject == ContextSymbol(
        id="repo:main.py:target:3",
        kind="Function",
        name="target",
        location=SourceLocation(
            file_path="main.py",
            start_line=3,
            end_line=5,
        ),
    )

    assert [symbol.location.file_path for symbol in context.callers] == [
        "a.py",
        "z.py",
    ]

    assert [symbol.location.file_path for symbol in context.callees] == [
        "b.py",
    ]

    assert [symbol.location.file_path for symbol in context.subclasses] == [
        "c.py",
    ]

    assert [file.file_path for file in context.importing_files] == [
        "a.py",
        "z.py",
    ]


def test_build_applies_context_limits_and_records_truncation():
    queries = FakeGraphQueries()

    context = ContextBuilder(queries).build(
        "repo:main.py:target:3",
        ContextLimits(
            max_callers=1,
            max_callees=0,
            max_subclasses=0,
            max_importing_files=1,
        ),
    )

    assert len(context.callers) == 1
    assert len(context.callees) == 0
    assert len(context.subclasses) == 0
    assert len(context.importing_files) == 1

    assert context.truncated_sections == (
        "callers",
        "callees",
        "subclasses",
        "importing_files",
    )


def test_build_uses_empty_importing_files_when_none_exist():
    queries = FakeGraphQueries()
    queries.importing_files = ()

    context = ContextBuilder(queries).build(
        "repo:main.py:target:3"
    )

    assert context.importing_files == ()


def test_negative_context_limits_are_rejected():
    with pytest.raises(
        ValueError,
        match="Context limits must be non-negative",
    ):
        ContextBuilder(FakeGraphQueries()).build(
            "repo:main.py:target:3",
            ContextLimits(max_importing_files=-1),
        )


def test_context_builder_preserves_empty_relationships():
    queries = FakeGraphQueries()

    queries.impact_result = FakeImpact(
        subject=queries.impact_result.subject,
        callers=(),
        callees=(),
        subclasses=(),
    )

    context = ContextBuilder(queries).build(
        "repo:main.py:target:3"
    )

    assert context.callers == ()
    assert context.callees == ()
    assert context.subclasses == ()

    assert context.importing_files == (
        ContextFile(
            id="repo:a.py",
            file_path="a.py",
            name="a",
        ),
        ContextFile(
            id="repo:z.py",
            file_path="z.py",
            name="z",
        ),
    )