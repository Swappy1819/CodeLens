"""LLM provider adapters for CodeLens."""

from typing import Callable

from .prompt_builder import PromptBuilder
from .review import ReviewRequest, ReviewResult
from .review_parser import parse_review_response


class CallableLLMProvider:
    """Adapt a callable LLM backend to the CodeLens provider interface."""

    def __init__(
        self,
        generate: Callable[[str], str],
        prompt_builder: PromptBuilder = None,
    ) -> None:
        self.generate = generate
        self.prompt_builder = prompt_builder or PromptBuilder()

    def review(self, request: ReviewRequest) -> ReviewResult:
        """Build a prompt, call the backend, and parse its response."""

        prompt = self.prompt_builder.build(request)
        response = self.generate(prompt)

        return parse_review_response(response)
