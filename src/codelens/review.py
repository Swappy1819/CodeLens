"""Structured result returned by a review operation."""

from dataclasses import dataclass
from typing import Optional, Protocol, Tuple

from .diff_parser import ChangedRange


@dataclass(frozen=True)
class ReviewFinding:
    """A single structured finding returned by an LLM review."""

    severity: str
    title: str
    description: str
    file_path: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class ReviewResult:
    """Structured result returned by a review operation."""

    findings: Tuple[ReviewFinding, ...]


@dataclass(frozen=True)
class ReviewRequest:
    """Backend-neutral review request passed to an LLM provider."""

    symbol_id: str
    file_path: str
    symbol_name: str
    symbol_type: str
    start_line: int
    end_line: Optional[int]
    source: str
    context: str
    changed_ranges: Tuple[ChangedRange, ...] = ()


class LLMProvider(Protocol):
    """Provider interface used by the review engine."""

    def review(self, request: ReviewRequest) -> ReviewResult:
        """Review a changed symbol and return structured findings."""
        ...


class ReviewEngine:
    """Orchestrate review requests through an LLM provider."""

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def review(self, request: ReviewRequest) -> ReviewResult:
        """Submit one review request to the configured LLM provider."""
        return self.provider.review(request)