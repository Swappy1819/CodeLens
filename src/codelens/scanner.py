"""Repository discovery utilities."""

from dataclasses import dataclass
from pathlib import Path
from typing import Union


IGNORED_DIRECTORIES = {".git", ".venv", "__pycache__", "node_modules"}


@dataclass(frozen=True)
class PythonFile:
    """Information about a Python source file in a repository."""

    path: Path
    name: str
    extension: str


def scan_repository(repository: Union[Path, str]) -> list[PythonFile]:
    """Return Python source files below *repository*, excluding ignored directories.

    Paths in the result are relative to the supplied repository directory.
    """
    repository_path = Path(repository).resolve()
    files: list[PythonFile] = []

    for entry in repository_path.iterdir():
        if entry.is_dir():
            if entry.name in IGNORED_DIRECTORIES or entry.name.startswith("."):
                continue
            files.extend(_scan_directory(entry, repository_path))
        elif entry.is_file() and entry.suffix == ".py":
            files.append(_file_info(entry, repository_path))

    return files


def _scan_directory(directory: Path, repository: Path) -> list[PythonFile]:
    files: list[PythonFile] = []

    for entry in directory.iterdir():
        if entry.is_dir():
            if entry.name in IGNORED_DIRECTORIES or entry.name.startswith("."):
                continue
            files.extend(_scan_directory(entry, repository))
        elif entry.is_file() and entry.suffix == ".py":
            files.append(_file_info(entry, repository))

    return files


def _file_info(path: Path, repository: Path) -> PythonFile:
    return PythonFile(
        path=path.relative_to(repository),
        name=path.name,
        extension=path.suffix,
    )
