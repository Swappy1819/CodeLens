from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import pytest

from codelens.review import ReviewResult
from codelens.review_parser import ReviewParseError, parse_review_response


def test_parses_valid_finding() -> None:
    response = """
    {
        "findings": [
            {
                "severity": "high",
                "title": "Potential bug",
                "description": "This can fail when the value is missing.",
                "file_path": "service.py",
                "start_line": 10,
                "end_line": 12
            }
        ]
    }
    """

    result = parse_review_response(response)

    assert len(result.findings) == 1
    assert result.findings[0].severity == "high"
    assert result.findings[0].start_line == 10
    assert result.findings[0].end_line == 12


def test_parses_empty_findings() -> None:
    result = parse_review_response('{"findings": []}')

    assert result == ReviewResult(findings=())


def test_rejects_invalid_json() -> None:
    with pytest.raises(ReviewParseError):
        parse_review_response("not json")


def test_rejects_missing_findings() -> None:
    with pytest.raises(ReviewParseError):
        parse_review_response("{}")


def test_rejects_invalid_severity() -> None:
    response = """
    {
        "findings": [
            {
                "severity": "urgent",
                "title": "Problem",
                "description": "Something is wrong.",
                "file_path": "service.py",
                "start_line": 1,
                "end_line": 1
            }
        ]
    }
    """

    with pytest.raises(ReviewParseError):
        parse_review_response(response)


def test_rejects_invalid_line_range() -> None:
    response = """
    {
        "findings": [
            {
                "severity": "medium",
                "title": "Problem",
                "description": "Something is wrong.",
                "file_path": "service.py",
                "start_line": 10,
                "end_line": 5
            }
        ]
    }
    """

    with pytest.raises(ReviewParseError):
        parse_review_response(response)


def test_rejects_non_object_finding() -> None:
    with pytest.raises(ReviewParseError):
        parse_review_response('{"findings": ["bad"]}')
