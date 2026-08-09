"""Bounded source retrieval for CodeLens review workflows."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class SourceSnippet:
    """A bounded section of source code."""

    symbol_id: str
    file_path: str
    start_line: int
    end_line: int
    content: str


class SourceProvider:
    """Read bounded source snippets from a repository."""

    def __init__(self, repository: Path) -> None:
        self.repository = repository.resolve()

    def get_source(
        self,
        symbol_id: str,
        file_path: str,
        start_line: int,
        end_line: Optional[int],
        max_lines: int = 100,
    ) -> Optional[SourceSnippet]:
        """Return source for a symbol, or None when it cannot be read."""

        if start_line < 1 or max_lines < 1:
            return None

        path = (self.repository / file_path).resolve()

        try:
            path.relative_to(self.repository)
        except ValueError:
            return None

        if not path.is_file():
            return None

        lines = path.read_text(encoding="utf-8").splitlines()

        if start_line > len(lines):
            return None

        requested_end = end_line if end_line is not None else start_line
        requested_end = max(start_line, requested_end)

        actual_end = min(
            requested_end,
            start_line + max_lines - 1,
            len(lines),
        )

        content = "\n".join(lines[start_line - 1 : actual_end])

        return SourceSnippet(
            symbol_id=symbol_id,
            file_path=file_path,
            start_line=start_line,
            end_line=actual_end,
            content=content,
        )