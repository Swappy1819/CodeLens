from types import SimpleNamespace

from codelens.gemini_provider import GeminiLLMProvider
from codelens.review import ReviewRequest


class FakeModels:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=self.response_text)


class FakeClient:
    def __init__(self, response_text: str) -> None:
        self.models = FakeModels(response_text)


def make_request() -> ReviewRequest:
    return ReviewRequest(
        symbol_id="repo:service.py:run:1",
        file_path="service.py",
        symbol_name="run",
        symbol_type="function",
        start_line=1,
        end_line=3,
        source="def run():\n    return 1",
        context="No callers or callees.",
    )


def test_gemini_provider_sends_prompt_to_backend() -> None:
    client = FakeClient(
        '{"findings": []}'
    )
    provider = GeminiLLMProvider(client=client)

    result = provider.review(make_request())

    assert result.findings == ()
    assert len(client.models.calls) == 1
    assert "service.py" in client.models.calls[0]["contents"]
    assert client.models.calls[0]["model"] == "gemini-3.6-flash"


def test_gemini_provider_parses_findings() -> None:
    client = FakeClient(
        """
        {
            "findings": [
                {
                    "severity": "high",
                    "title": "Potential bug",
                    "description": "The value may be incorrect.",
                    "file_path": "service.py",
                    "start_line": 2,
                    "end_line": 2
                }
            ]
        }
        """
    )

    provider = GeminiLLMProvider(client=client)

    result = provider.review(make_request())

    assert len(result.findings) == 1
    assert result.findings[0].severity == "high"
    assert result.findings[0].title == "Potential bug"
    assert result.findings[0].file_path == "service.py"
    assert result.findings[0].start_line == 2


def test_gemini_provider_calls_backend_once() -> None:
    client = FakeClient('{"findings": []}')
    provider = GeminiLLMProvider(client=client)

    provider.review(make_request())

    assert len(client.models.calls) == 1