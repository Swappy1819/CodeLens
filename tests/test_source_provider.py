from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from codelens.source_provider import SourceProvider


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_reads_exact_symbol_source(tmp_path: Path) -> None:
    write(
        tmp_path / "service.py",
        "line 1\nline 2\nline 3\nline 4\n",
    )

    provider = SourceProvider(tmp_path)

    result = provider.get_source(
        "repo:service.py:run:2",
        "service.py",
        2,
        3,
    )

    assert result is not None
    assert result.file_path == "service.py"
    assert result.start_line == 2
    assert result.end_line == 3
    assert result.content == "line 2\nline 3"


def test_bounds_source_by_max_lines(tmp_path: Path) -> None:
    write(
        tmp_path / "service.py",
        "1\n2\n3\n4\n5\n",
    )

    provider = SourceProvider(tmp_path)

    result = provider.get_source(
        "repo:service.py:run:1",
        "service.py",
        1,
        5,
        max_lines=2,
    )

    assert result is not None
    assert result.end_line == 2
    assert result.content == "1\n2"


def test_none_end_line_reads_one_line(tmp_path: Path) -> None:
    write(
        tmp_path / "service.py",
        "1\n2\n3\n",
    )

    provider = SourceProvider(tmp_path)

    result = provider.get_source(
        "repo:service.py:run:2",
        "service.py",
        2,
        None,
    )

    assert result is not None
    assert result.content == "2"


def test_missing_file_returns_none(tmp_path: Path) -> None:
    provider = SourceProvider(tmp_path)

    assert (
        provider.get_source(
            "repo:missing.py:run:1",
            "missing.py",
            1,
            2,
        )
        is None
    )


def test_out_of_range_start_line_returns_none(tmp_path: Path) -> None:
    write(tmp_path / "service.py", "1\n2\n")

    provider = SourceProvider(tmp_path)

    assert (
        provider.get_source(
            "repo:service.py:run:10",
            "service.py",
            10,
            12,
        )
        is None
    )


def test_rejects_path_outside_repository(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.py"
    write(outside, "secret\n")

    provider = SourceProvider(tmp_path)

    assert (
        provider.get_source(
            "repo:../outside.py:run:1",
            "../outside.py",
            1,
            1,
        )
        is None
    )