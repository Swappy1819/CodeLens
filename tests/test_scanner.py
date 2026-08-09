from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from codelens.scanner import scan_repository


def create_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# test file\n")


def test_discovers_python_files_recursively_with_metadata(tmp_path: Path) -> None:
    create_file(tmp_path / "main.py")
    create_file(tmp_path / "package" / "module.py")
    create_file(tmp_path / "package" / "nested" / "helpers.py")

    files = scan_repository(tmp_path)

    assert {file.path for file in files} == {
        Path("main.py"),
        Path("package/module.py"),
        Path("package/nested/helpers.py"),
    }
    main_file = next(file for file in files if file.path == Path("main.py"))
    assert main_file.name == "main.py"
    assert main_file.extension == ".py"


def test_ignores_non_python_files(tmp_path: Path) -> None:
    create_file(tmp_path / "source.py")
    create_file(tmp_path / "notes.txt")
    create_file(tmp_path / "frontend" / "app.js")

    files = scan_repository(tmp_path)

    assert [file.path for file in files] == [Path("source.py")]


def test_does_not_scan_ignored_or_hidden_directories(tmp_path: Path) -> None:
    create_file(tmp_path / "included.py")
    for directory in (".git", ".venv", "__pycache__", "node_modules", ".hidden"):
        create_file(tmp_path / directory / "excluded.py")

    files = scan_repository(tmp_path)

    assert [file.path for file in files] == [Path("included.py")]
