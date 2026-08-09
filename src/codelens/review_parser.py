"""Structured LLM review response parsing for CodeLens."""

import json
from typing import Any, List

from .review import ReviewFinding, ReviewResult


_ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}


class ReviewParseError(ValueError):
    """Raised when an LLM review response is invalid."""


def parse_review_response(response: str) -> ReviewResult:
    """Parse and validate a JSON review response."""

    try:
        payload = json.loads(response)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ReviewParseError("Review response is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ReviewParseError("Review response must be a JSON object.")

    findings = payload.get("findings")

    if not isinstance(findings, list):
        raise ReviewParseError("'findings' must be a JSON array.")

    parsed: List[ReviewFinding] = []

    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise ReviewParseError(
                f"Finding {index} must be a JSON object."
            )

        severity = finding.get("severity")
        title = finding.get("title")
        description = finding.get("description")
        file_path = finding.get("file_path")
        start_line = finding.get("start_line")
        end_line = finding.get("end_line")

        if severity not in _ALLOWED_SEVERITIES:
            raise ReviewParseError(
                f"Finding {index} has an invalid severity."
            )

        if not isinstance(title, str) or not title.strip():
            raise ReviewParseError(
                f"Finding {index} must have a non-empty title."
            )

        if not isinstance(description, str) or not description.strip():
            raise ReviewParseError(
                f"Finding {index} must have a non-empty description."
            )

        if not isinstance(file_path, str) or not file_path.strip():
            raise ReviewParseError(
                f"Finding {index} must have a non-empty file_path."
            )

        if not isinstance(start_line, int) or isinstance(start_line, bool):
            raise ReviewParseError(
                f"Finding {index} must have an integer start_line."
            )

        if not isinstance(end_line, int) or isinstance(end_line, bool):
            raise ReviewParseError(
                f"Finding {index} must have an integer end_line."
            )

        if start_line < 1 or end_line < start_line:
            raise ReviewParseError(
                f"Finding {index} has an invalid line range."
            )

        parsed.append(
            ReviewFinding(
                severity=severity,
                title=title,
                description=description,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
            )
        )

    return ReviewResult(findings=tuple(parsed))
