from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from codelens.prompt_builder import PromptBuilder
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


def test_build_contains_review_request_information() -> None:
    prompt = PromptBuilder().build(make_request())

    assert "repo:service.py:run:10" in prompt
    assert "run" in prompt
    assert "method" in prompt
    assert "service.py" in prompt
    assert "10-15" in prompt
    assert "return value" in prompt
    assert "caller: service.py:caller" in prompt


def test_build_is_deterministic() -> None:
    builder = PromptBuilder()
    request = make_request()

    assert builder.build(request) == builder.build(request)


def test_build_contains_source_and_context_boundaries() -> None:
    prompt = PromptBuilder().build(make_request())

    assert "Source:" in prompt
    assert "```python" in prompt
    assert "Graph context:" in prompt
    assert "Do not invent behavior or dependencies." in prompt
