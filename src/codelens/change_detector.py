"""Map Git changes to CodeLens symbols."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

from .analyzer import FileAnalysis, Symbol, analyze_repository
from .diff_parser import ChangedFile, ChangedRange


@dataclass(frozen=True)
class ChangedSymbol:
    """A symbol affected by a change in its current source."""

    id: str
    name: str
    symbol_type: str
    file_path: str
    start_line: int
    end_line: int
    parent_name: Optional[str] = None
    changed_ranges: Tuple[ChangedRange, ...] = ()


def symbol_id(repository: Path, symbol: Symbol) -> str:
    """Build the stable graph ID for a symbol."""
    repository_name = repository.resolve().name

    parts = [
        repository_name,
        symbol.file_path.as_posix(),
    ]

    if symbol.symbol_type == "method" and symbol.parent_name:
        parts.append(symbol.parent_name)

    parts.extend([symbol.name, str(symbol.start_line)])

    return ":".join(parts)


def _ranges_overlap(
    start_line: int,
    end_line: int,
    changed_file: ChangedFile,
) -> bool:
    return any(
        start_line <= changed.end_line
        and end_line >= changed.start_line
        for changed in changed_file.ranges
    )


def _matching_ranges(
    start_line: int,
    end_line: int,
    changed_file: ChangedFile,
) -> Tuple[ChangedRange, ...]:
    return tuple(
        changed
        for changed in changed_file.ranges
        if start_line <= changed.end_line
        and end_line >= changed.start_line
    )


def _to_changed_symbol(
    repository: Path,
    symbol: Symbol,
    changed_ranges: Tuple[ChangedRange, ...],
) -> ChangedSymbol:
    return ChangedSymbol(
        id=symbol_id(repository, symbol),
        name=symbol.name,
        symbol_type=symbol.symbol_type,
        file_path=symbol.file_path.as_posix(),
        start_line=symbol.start_line,
        end_line=symbol.end_line,
        parent_name=symbol.parent_name,
        changed_ranges=changed_ranges,
    )


def detect_changed_symbols(
    repository: Union[Path, str],
    changed_files: List[ChangedFile],
) -> List[ChangedSymbol]:
    """Return current symbols touched by changed new-file lines.

    Changes outside symbols are intentionally ignored. Deleted-only files
    cannot be resolved against the current AST and therefore produce no
    ChangedSymbol.
    """
    repository_path = Path(repository).resolve()
    analyses = analyze_repository(repository_path)

    analysis_by_path = {
        analysis.file_path.as_posix(): analysis
        for analysis in analyses
    }

    changed_symbols: dict[str, ChangedSymbol] = {}

    for changed_file in changed_files:
        if not changed_file.ranges or changed_file.is_deleted:
            continue

        analysis = analysis_by_path.get(changed_file.file_path)
        if analysis is None:
            continue

        matching_symbols = [
            symbol
            for symbol in analysis.symbols
            if _ranges_overlap(
                symbol.start_line,
                symbol.end_line,
                changed_file,
            )
        ]

        for symbol in matching_symbols:
            if symbol.symbol_type == "class":
                has_more_specific_match = any(
                    other.symbol_type in {"function", "method"}
                    and other.start_line >= symbol.start_line
                    and other.end_line <= symbol.end_line
                    for other in matching_symbols
                )
                if has_more_specific_match:
                    continue

            ranges = _matching_ranges(
                symbol.start_line,
                symbol.end_line,
                changed_file,
            )

            result = _to_changed_symbol(
                repository_path,
                symbol,
                ranges,
            )
            changed_symbols[result.id] = result

    return sorted(
        changed_symbols.values(),
        key=lambda item: (
            item.file_path,
            item.start_line,
            item.id,
        ),
    )