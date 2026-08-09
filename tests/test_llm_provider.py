from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from codelens.llm_provider import CallableLLMProvider
from codelens.review import ReviewRequest


def make_request() -> ReviewRequest:
    return ReviewRequest(
        symbol_id="repo:service.py:run:10",
        file_path="service.py",
        symbol_name="run",
        symbol_type="method",
        start_line=10,
        end_line=15,
        source="return value",
        context="caller: service.py:caller",
    )


def test_provider_builds_prompt_calls_backend_and_parses_response() -> None:
    calls = []

    def fake_generate(prompt: str) -> str:
        calls.append(prompt)
        return """
        {
            "findings": [
                {
                    "severity": "high",
                    "title": "Potential bug",
                    "description": "The value may be missing.",
                    "file_path": "service.py",
                    "start_line": 10,
                    "end_line": 10
                }
            ]
        }
        """

    provider = CallableLLMProvider(fake_generate)

    result = provider.review(make_request())

    assert len(calls) == 1
    assert "repo:service.py:run:10" in calls[0]
    assert result.findings[0].severity == "high"
    assert result.findings[0].file_path == "service.py"


def test_provider_preserves_empty_result() -> None:
    def fake_generate(prompt: str) -> str:
        return '{"findings": []}'

    provider = CallableLLMProvider(fake_generate)

    result = provider.review(make_request())

    assert result.findings == ()


def test_provider_calls_backend_once() -> None:
    count = 0

    def fake_generate(prompt: str) -> str:
        nonlocal count
        count += 1
        return '{"findings": []}'

    provider = CallableLLMProvider(fake_generate)

    provider.review(make_request())

    assert count == 1
