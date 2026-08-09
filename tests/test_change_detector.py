from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from codelens.change_detector import detect_changed_symbols
from codelens.diff_parser import ChangedFile, ChangedRange


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_detects_changed_function(tmp_path: Path) -> None:
    write(
        tmp_path / "main.py",
        """\
def helper():
    return 1

def checkout():
    return helper()
""",
    )

    changed = [
        ChangedFile(
            file_path="main.py",
            ranges=(ChangedRange(5, 5),),
        )
    ]

    result = detect_changed_symbols(tmp_path, changed)

    assert len(result) == 1
    assert result[0].name == "checkout"
    assert result[0].symbol_type == "function"
    assert result[0].file_path == "main.py"
    assert result[0].start_line == 4
    assert result[0].end_line == 5


def test_detects_changed_method(tmp_path: Path) -> None:
    write(
        tmp_path / "service.py",
        """\
class Service:
    def run(self):
        return 1
""",
    )

    changed = [
        ChangedFile(
            file_path="service.py",
            ranges=(ChangedRange(3, 3),),
        )
    ]

    result = detect_changed_symbols(tmp_path, changed)

    assert len(result) == 1
    assert result[0].name == "run"
    assert result[0].symbol_type == "method"
    assert result[0].parent_name == "Service"


def test_detects_multiple_symbols_from_multiple_files(tmp_path: Path) -> None:
    write(
        tmp_path / "a.py",
        """\
def first():
    return 1
""",
    )
    write(
        tmp_path / "b.py",
        """\
def second():
    return 2
""",
    )

    changed = [
        ChangedFile("a.py", (ChangedRange(2, 2),)),
        ChangedFile("b.py", (ChangedRange(2, 2),)),
    ]

    result = detect_changed_symbols(tmp_path, changed)

    assert [item.name for item in result] == ["first", "second"]


def test_deduplicates_symbol_touched_by_multiple_hunks(tmp_path: Path) -> None:
    write(
        tmp_path / "main.py",
        """\
def checkout():
    first = 1
    second = 2
    return first + second
""",
    )

    changed = [
        ChangedFile(
            file_path="main.py",
            ranges=(
                ChangedRange(2, 2),
                ChangedRange(4, 4),
            ),
        )
    ]

    result = detect_changed_symbols(tmp_path, changed)

    assert len(result) == 1
    assert result[0].name == "checkout"


def test_ignores_changes_outside_symbols(tmp_path: Path) -> None:
    write(
        tmp_path / "main.py",
        """\
# module comment

def checkout():
    return 1
""",
    )

    changed = [
        ChangedFile(
            file_path="main.py",
            ranges=(ChangedRange(1, 1),),
        )
    ]

    result = detect_changed_symbols(tmp_path, changed)

    assert result == []


def test_ignores_deleted_only_file(tmp_path: Path) -> None:
    changed = [
        ChangedFile(
            file_path="deleted.py",
            ranges=(),
            is_deleted=True,
        )
    ]

    result = detect_changed_symbols(tmp_path, changed)

    assert result == []


def test_ignores_unknown_file(tmp_path: Path) -> None:
    changed = [
        ChangedFile(
            file_path="missing.py",
            ranges=(ChangedRange(1, 3),),
        )
    ]

    result = detect_changed_symbols(tmp_path, changed)

    assert result == []
