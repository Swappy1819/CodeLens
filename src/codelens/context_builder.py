"""Bounded, backend-neutral context for CodeLens review workflows."""

from dataclasses import dataclass
from typing import Optional, Tuple

from .graph_queries import FileRef


@dataclass(frozen=True)
class ContextLimits:
    max_callers: int = 10
    max_callees: int = 10
    max_subclasses: int = 10
    max_importing_files: int = 10


@dataclass(frozen=True)
class SourceLocation:
    file_path: str
    start_line: int
    end_line: Optional[int]


@dataclass(frozen=True)
class ContextSymbol:
    id: str
    kind: str
    name: str
    location: SourceLocation


@dataclass(frozen=True)
class ContextFile:
    id: str
    file_path: str
    name: str


@dataclass(frozen=True)
class SymbolContext:
    subject: Optional[ContextSymbol]
    callers: Tuple[ContextSymbol, ...]
    callees: Tuple[ContextSymbol, ...]
    subclasses: Tuple[ContextSymbol, ...]
    importing_files: Tuple[ContextFile, ...]
    truncated_sections: Tuple[str, ...]


class ContextBuilder:
    """Build bounded context from a graph-query service interface."""

    def __init__(self, graph_queries) -> None:
        self.graph_queries = graph_queries

    def build(
        self,
        symbol_id: str,
        limits: Optional[ContextLimits] = None,
    ) -> SymbolContext:
        """Return direct graph context for one stable symbol ID."""
        limits = limits or ContextLimits()
        self._validate_limits(limits)

        impact = self.graph_queries.impact(symbol_id)
        truncated_sections = []

        callers = self._bounded_symbols(
            impact.callers,
            limits.max_callers,
            "callers",
            truncated_sections,
        )

        callees = self._bounded_symbols(
            impact.callees,
            limits.max_callees,
            "callees",
            truncated_sections,
        )

        subclasses = self._bounded_symbols(
            impact.subclasses,
            limits.max_subclasses,
            "subclasses",
            truncated_sections,
        )

        importing_files = self._bounded_files(
            self.graph_queries.files_importing_symbol_module(symbol_id),
            limits.max_importing_files,
            "importing_files",
            truncated_sections,
        )

        return SymbolContext(
            subject=(
                self._to_context_symbol(impact.subject)
                if impact.subject is not None
                else None
            ),
            callers=callers,
            callees=callees,
            subclasses=subclasses,
            importing_files=importing_files,
            truncated_sections=tuple(truncated_sections),
        )

    @classmethod
    def _bounded_symbols(
        cls,
        entities,
        limit: int,
        section: str,
        truncated_sections: list,
    ) -> Tuple[ContextSymbol, ...]:
        symbols = sorted(
            (cls._to_context_symbol(entity) for entity in entities),
            key=lambda symbol: (
                symbol.location.file_path,
                symbol.location.start_line,
                symbol.id,
            ),
        )

        if len(symbols) > limit:
            truncated_sections.append(section)

        return tuple(symbols[:limit])

    @staticmethod
    def _bounded_files(
        files,
        limit: int,
        section: str,
        truncated_sections: list,
    ) -> Tuple[ContextFile, ...]:
        context_files = sorted(
            (
                ContextFile(
                    id=file.id,
                    file_path=file.file_path,
                    name=file.name,
                )
                for file in files
            ),
            key=lambda file: (file.file_path, file.id),
        )

        if len(context_files) > limit:
            truncated_sections.append(section)

        return tuple(context_files[:limit])

    @staticmethod
    def _to_context_symbol(entity) -> ContextSymbol:
        return ContextSymbol(
            id=entity.id,
            kind=entity.kind,
            name=entity.name,
            location=SourceLocation(
                file_path=entity.file_path,
                start_line=entity.start_line,
                end_line=entity.end_line,
            ),
        )

    @staticmethod
    def _validate_limits(limits: ContextLimits) -> None:
        if min(
            limits.max_callers,
            limits.max_callees,
            limits.max_subclasses,
            limits.max_importing_files,
        ) < 0:
            raise ValueError("Context limits must be non-negative")