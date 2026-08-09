from pathlib import Path
from types import SimpleNamespace

from codelens.change_detector import ChangedSymbol
from codelens.context_builder import ContextLimits
from codelens.review_workflow import ReviewWorkflow


class FakeSource:
    content = "def target():\n    return 1\n"


class FakeSourceProvider:
    def __init__(self, repository):
        self.repository = repository

    def get_source(
        self,
        symbol_id,
        file_path,
        start_line,
        end_line,
    ):
        return FakeSource()


class FakeGraphQueries:
    def impact(self, symbol_id):
        return SimpleNamespace(
            subject=None,
            callers=(),
            callees=(),
            subclasses=(),
        )

    def files_importing_symbol_module(self, symbol_id):
        return ()


class FakeReviewEngine:
    def __init__(self, provider):
        self.provider = provider
        self.requests = []

    def review(self, request):
        self.requests.append(request)
        return SimpleNamespace(
            findings=(
                SimpleNamespace(
                    title="Test finding",
                ),
            )
        )


def test_review_workflow_connects_change_to_provider(monkeypatch):
    changed_symbol = ChangedSymbol(
        id="repo:main.py:target:1",
        file_path="main.py",
        name="target",
        symbol_type="Function",
        start_line=1,
        end_line=2,
    )

    monkeypatch.setattr(
        "codelens.review_workflow.parse_git_diff",
        lambda diff_text: (),
    )

    monkeypatch.setattr(
        "codelens.review_workflow.detect_changed_symbols",
        lambda repository, changed_files: (changed_symbol,),
    )

    monkeypatch.setattr(
        "codelens.review_workflow.SourceProvider",
        FakeSourceProvider,
    )

    monkeypatch.setattr(
        "codelens.review_workflow.ReviewEngine",
        FakeReviewEngine,
    )

    workflow = ReviewWorkflow(
        repository=Path("."),
        graph_queries=FakeGraphQueries(),
        provider=object(),
        context_limits=ContextLimits(),
    )

    result = workflow.review("diff")

    assert len(result.findings) == 1
    assert result.findings[0].title == "Test finding"


def test_review_workflow_formats_repository_context(monkeypatch):
    changed_symbol = ChangedSymbol(
        id="repo:main.py:target:1",
        file_path="main.py",
        name="target",
        symbol_type="Function",
        start_line=1,
        end_line=2,
    )

    monkeypatch.setattr(
        "codelens.review_workflow.parse_git_diff",
        lambda diff_text: (),
    )

    monkeypatch.setattr(
        "codelens.review_workflow.detect_changed_symbols",
        lambda repository, changed_files: (changed_symbol,),
    )

    monkeypatch.setattr(
        "codelens.review_workflow.SourceProvider",
        FakeSourceProvider,
    )

    captured = {}

    class CapturingReviewEngine:
        def __init__(self, provider):
            pass

        def review(self, request):
            captured["request"] = request
            return SimpleNamespace(findings=())

    monkeypatch.setattr(
        "codelens.review_workflow.ReviewEngine",
        CapturingReviewEngine,
    )

    graph_queries = FakeGraphQueries()

    workflow = ReviewWorkflow(
        repository=Path("."),
        graph_queries=graph_queries,
        provider=object(),
        context_limits=ContextLimits(),
    )

    workflow.review("diff")

    context = captured["request"].context

    assert "Callers:" in context
    assert "Callees:" in context
    assert "Subclasses:" in context
    assert "Importing files:" in context
    assert "- None" in context