"""Gemini LLM provider for CodeLens."""

import os
from typing import Optional

from google import genai

from .prompt_builder import PromptBuilder
from .review import ReviewRequest, ReviewResult
from .review_parser import parse_review_response


class GeminiLLMProvider:
    """Use Google's Gemini API as a CodeLens LLM provider."""

    def __init__(
        self,
        client=None,
        model: str = "gemini-2.5-flash",
        prompt_builder: Optional[PromptBuilder] = None,
    ) -> None:
        self.client = client or genai.Client(
            api_key=os.environ["GEMINI_API_KEY"]
        )
        self.model = model
        self.prompt_builder = prompt_builder or PromptBuilder()

    def review(self, request: ReviewRequest) -> ReviewResult:
        """Build a review prompt, call Gemini, and parse its response."""

        prompt = self.prompt_builder.build(request)

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
            },
        )

        return parse_review_response(response.text)