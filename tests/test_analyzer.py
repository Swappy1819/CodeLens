from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from codelens.analyzer import analyze_repository


def write_python_file(repository: Path, relative_path: str, contents: str) -> None:
    path = repository / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)


def test_extracts_top_level_functions(tmp_path: Path) -> None:
    write_python_file(
        tmp_path,
        "module.py",
        "def greet(name):\n    return f'Hello, {name}'\n",
    )

    analysis = analyze_repository(tmp_path)[0]

    assert [(symbol.name, symbol.symbol_type) for symbol in analysis.symbols] == [
        ("greet", "function")
    ]


def test_extracts_classes_and_their_methods(tmp_path: Path) -> None:
    write_python_file(
        tmp_path,
        "models/user.py",
        "class User:\n    def display_name(self):\n        return 'Ada'\n",
    )

    analysis = analyze_repository(tmp_path)[0]

    assert [(symbol.name, symbol.symbol_type) for symbol in analysis.symbols] == [
        ("User", "class"),
        ("display_name", "method"),
    ]
    method = analysis.symbols[1]
    assert method.parent_name == "User"
    assert method.file_path == Path("models/user.py")


def test_extracts_imports_and_from_imports(tmp_path: Path) -> None:
    write_python_file(
        tmp_path,
        "imports.py",
        "import os\nimport pathlib as paths\nfrom collections import defaultdict\nfrom math import sqrt as root\n",
    )

    symbols = analyze_repository(tmp_path)[0].symbols

    assert [(symbol.name, symbol.symbol_type, symbol.module) for symbol in symbols] == [
        ("os", "import", "os"),
        ("paths", "import", "pathlib"),
        ("defaultdict", "from_import", "collections"),
        ("root", "from_import", "math"),
    ]


def test_records_symbol_line_numbers(tmp_path: Path) -> None:
    write_python_file(
        tmp_path,
        "lines.py",
        "\n\ndef one_line():\n    pass\n",
    )

    symbol = analyze_repository(tmp_path)[0].symbols[0]

    assert symbol.start_line == 3
    assert symbol.end_line == 4


def test_invalid_python_file_does_not_stop_repository_analysis(tmp_path: Path) -> None:
    write_python_file(tmp_path, "valid.py", "def valid():\n    pass\n")
    write_python_file(tmp_path, "invalid.py", "def broken(:\n    pass\n")

    analyses = {analysis.file_path: analysis for analysis in analyze_repository(tmp_path)}

    assert analyses[Path("invalid.py")].symbols == []
    assert analyses[Path("invalid.py")].syntax_error is not None
    assert analyses[Path("valid.py")].symbols[0].name == "valid"
