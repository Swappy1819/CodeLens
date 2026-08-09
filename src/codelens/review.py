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
        """Submit one review request and keep only in-scope findings."""

        result = self.provider.review(request)

        # Preserve backend-neutral behavior for callers that do not
        # provide explicit Git changed ranges.
        if not request.changed_ranges:
            return result

        findings = tuple(
            finding
            for finding in result.findings
            if self._is_in_scope(finding, request)
        )

        return ReviewResult(findings=findings)

    @staticmethod
    def _is_in_scope(
        finding: ReviewFinding,
        request: ReviewRequest,
    ) -> bool:
        """Return whether a finding overlaps the actual changed lines."""

        if finding.file_path != request.file_path:
            return False

        return any(
            finding.start_line <= changed.end_line
            and finding.end_line >= changed.start_line
            for changed in request.changed_ranges
        )