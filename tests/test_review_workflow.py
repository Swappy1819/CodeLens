from pathlib import Path
from types import SimpleNamespace

from codelens.change_detector import ChangedSymbol
from codelens.context_builder import ContextLimits
from codelens.diff_parser import ChangedRange
from codelens.review import ReviewFinding, ReviewResult
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

def test_review_workflow_includes_verified_callee_source(monkeypatch):
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

    class CalleeSourceProvider:
        def __init__(self, repository):
            self.repository = repository

        def get_source(
            self,
            symbol_id,
            file_path,
            start_line,
            end_line,
        ):
            if file_path == "pricing.py":
                return SimpleNamespace(
                    content=(
                        "def apply_discount(total, discount):\n"
                        "    return total * (1 - discount)\n"
                    )
                )

            return SimpleNamespace(
                content="def target():\n    return 1\n"
            )

    monkeypatch.setattr(
        "codelens.review_workflow.SourceProvider",
        CalleeSourceProvider,
    )

    class GraphWithCallee:
        def impact(self, symbol_id):
            return SimpleNamespace(
                subject=None,
                callers=(),
                callees=(
                    SimpleNamespace(
                        id="repo:pricing.py:apply_discount:1",
                        name="apply_discount",
                        kind="Function",
                        file_path="pricing.py",
                        start_line=1,
                        end_line=2,
                    ),
                ),
                subclasses=(),
            )

        def files_importing_symbol_module(self, symbol_id):
            return ()

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

    workflow = ReviewWorkflow(
        repository=Path("."),
        graph_queries=GraphWithCallee(),
        provider=object(),
        context_limits=ContextLimits(),
    )

    workflow.review("diff")

    context = captured["request"].context

    assert "Verified callee source:" in context
    assert "apply_discount" in context
    assert "return total * (1 - discount)" in context

def test_review_workflow_filters_out_of_scope_findings(monkeypatch):
    changed_symbol = ChangedSymbol(
        id="repo:main.py:target:1",
        file_path="main.py",
        name="target",
        symbol_type="Function",
        start_line=1,
        end_line=2,
        changed_ranges=(
            ChangedRange(start_line=1, end_line=1),
        ),
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

    class FakeProvider:
        def review(self, request):
            return ReviewResult(
                findings=(
                    ReviewFinding(
                        severity="high",
                        title="Real changed-code problem",
                        description="Problem in changed code.",
                        file_path="main.py",
                        start_line=1,
                        end_line=1,
                    ),
                    ReviewFinding(
                        severity="high",
                        title="Unrelated file problem",
                        description="Problem in another file.",
                        file_path="other.py",
                        start_line=1,
                        end_line=1,
                    ),
                    ReviewFinding(
                        severity="high",
                        title="Unchanged code problem",
                        description="Problem outside the change.",
                        file_path="main.py",
                        start_line=10,
                        end_line=10,
                    ),
                )
            )

    workflow = ReviewWorkflow(
        repository=Path("."),
        graph_queries=FakeGraphQueries(),
        provider=FakeProvider(),
        context_limits=ContextLimits(),
    )

    result = workflow.review("diff")

    assert len(result.findings) == 1
    assert result.findings[0].title == "Real changed-code problem"


def test_review_workflow_reviews_all_changed_symbols(monkeypatch):
    first_symbol = ChangedSymbol(
        id="repo:main.py:first:1",
        file_path="main.py",
        name="first",
        symbol_type="Function",
        start_line=1,
        end_line=2,
        changed_ranges=(
            ChangedRange(start_line=1, end_line=1),
        ),
    )

    second_symbol = ChangedSymbol(
        id="repo:main.py:second:5",
        file_path="main.py",
        name="second",
        symbol_type="Function",
        start_line=5,
        end_line=6,
        changed_ranges=(
            ChangedRange(start_line=5, end_line=5),
        ),
    )

    monkeypatch.setattr(
        "codelens.review_workflow.parse_git_diff",
        lambda diff_text: (),
    )

    monkeypatch.setattr(
        "codelens.review_workflow.detect_changed_symbols",
        lambda repository, changed_files: (
            first_symbol,
            second_symbol,
        ),
    )

    monkeypatch.setattr(
        "codelens.review_workflow.SourceProvider",
        FakeSourceProvider,
    )

    class FakeProvider:
        def review(self, request):
            return ReviewResult(
                findings=(
                    ReviewFinding(
                        severity="high",
                        title=f"Finding for {request.symbol_name}",
                        description="Test finding.",
                        file_path=request.file_path,
                        start_line=request.start_line,
                        end_line=request.start_line,
                    ),
                )
            )

    workflow = ReviewWorkflow(
        repository=Path("."),
        graph_queries=FakeGraphQueries(),
        provider=FakeProvider(),
        context_limits=ContextLimits(),
    )

    result = workflow.review("diff")

    assert len(result.findings) == 2
    assert result.findings[0].title == "Finding for first"
    assert result.findings[1].title == "Finding for second"