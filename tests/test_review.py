from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from codelens.review import ReviewEngine, ReviewFinding, ReviewRequest, ReviewResult


def test_review_finding_is_immutable() -> None:
    finding = ReviewFinding(
        severity="high",
        title="Unsafe operation",
        description="Potential problem.",
        file_path="service.py",
        start_line=10,
        end_line=12,
    )

    assert finding.severity == "high"
    assert finding.file_path == "service.py"

    try:
        finding.severity = "low"
    except AttributeError:
        pass
    else:
        raise AssertionError("ReviewFinding must be immutable")


def test_review_result_contains_findings() -> None:
    finding = ReviewFinding(
        severity="medium",
        title="Potential bug",
        description="Check this condition.",
        file_path="service.py",
        start_line=4,
        end_line=4,
    )

    result = ReviewResult(findings=(finding,))

    assert result.findings == (finding,)


def test_review_request_is_backend_neutral() -> None:
    request = ReviewRequest(
        symbol_id="repo:service.py:run:10",
        file_path="service.py",
        symbol_name="run",
        symbol_type="method",
        start_line=10,
        end_line=15,
        source="return value",
        context="caller: service.py:caller",
    )

    assert request.symbol_id == "repo:service.py:run:10"
    assert request.source == "return value"
    assert request.context == "caller: service.py:caller"


class FakeLLMProvider:
    def __init__(self, result: ReviewResult) -> None:
        self.result = result
        self.requests = []

    def review(self, request: ReviewRequest) -> ReviewResult:
        self.requests.append(request)
        return self.result


def test_review_engine_delegates_to_provider() -> None:
    finding = ReviewFinding(
        severity="high",
        title="Potential bug",
        description="Something looks wrong.",
        file_path="service.py",
        start_line=10,
        end_line=10,
    )
    expected = ReviewResult(findings=(finding,))
    provider = FakeLLMProvider(expected)
    engine = ReviewEngine(provider)

    request = ReviewRequest(
        symbol_id="repo:service.py:run:10",
        file_path="service.py",
        symbol_name="run",
        symbol_type="method",
        start_line=10,
        end_line=10,
        source="return value",
        context="caller: service.py:caller",
    )

    result = engine.review(request)

    assert result == expected
    assert provider.requests == [request]


def test_review_engine_preserves_empty_result() -> None:
    expected = ReviewResult(findings=())
    provider = FakeLLMProvider(expected)
    engine = ReviewEngine(provider)

    request = ReviewRequest(
        symbol_id="repo:service.py:run:1",
        file_path="service.py",
        symbol_name="run",
        symbol_type="method",
        start_line=1,
        end_line=1,
        source="pass",
        context="",
    )

    assert engine.review(request) == expected
