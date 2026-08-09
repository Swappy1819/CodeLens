"""Connect repository changes to structured CodeLens review findings."""

from pathlib import Path
from typing import Optional

from .change_detector import ChangedSymbol, detect_changed_symbols
from .context_builder import ContextBuilder, ContextLimits, SymbolContext
from .diff_parser import parse_git_diff
from .review import ReviewEngine, ReviewRequest, ReviewResult
from .source_provider import SourceProvider


class ReviewWorkflow:
    """Connect repository changes to structured CodeLens review findings."""

    def __init__(
        self,
        repository: Path,
        graph_queries,
        provider,
        context_limits: ContextLimits = None,
    ) -> None:
        self.repository = repository.resolve()
        self.context_builder = ContextBuilder(graph_queries)
        self.source_provider = SourceProvider(self.repository)
        self.review_engine = ReviewEngine(provider)
        self.context_limits = context_limits or ContextLimits()

    def review(self, diff_text: str) -> ReviewResult:
        """Review all current symbols affected by the supplied Git diff."""

        changed_files = parse_git_diff(diff_text)
        changed_symbols = detect_changed_symbols(
            self.repository,
            changed_files,
        )

        findings = []

        for symbol in changed_symbols:
            request = self._build_request(symbol)

            if request is None:
                continue

            result = self.review_engine.review(request)
            findings.extend(result.findings)

        return ReviewResult(findings=tuple(findings))

    def _build_request(
        self,
        symbol: ChangedSymbol,
    ) -> Optional[ReviewRequest]:
        source = self.source_provider.get_source(
            symbol_id=symbol.id,
            file_path=symbol.file_path,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
        )

        if source is None:
            return None

        context = self.context_builder.build(
            symbol.id,
            self.context_limits,
        )

        return ReviewRequest(
            symbol_id=symbol.id,
            file_path=symbol.file_path,
            symbol_name=symbol.name,
            symbol_type=symbol.symbol_type,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
            source=source.content,
            context=self._format_context(context),
            changed_ranges=symbol.changed_ranges,
        )

    @staticmethod
    def _format_context(context: SymbolContext) -> str:
        """Format structured repository context for the LLM."""

        sections = []

        if context.subject is not None:
            subject = context.subject
            sections.append(
                "Subject:\n"
                f"- {subject.kind} {subject.name} "
                f"({subject.location.file_path}:"
                f"{subject.location.start_line}-"
                f"{subject.location.end_line})"
            )

        sections.append(
            ReviewWorkflow._format_symbols(
                "Callers",
                context.callers,
            )
        )

        sections.append(
            ReviewWorkflow._format_symbols(
                "Callees",
                context.callees,
            )
        )

        sections.append(
            ReviewWorkflow._format_symbols(
                "Subclasses",
                context.subclasses,
            )
        )

        sections.append(
            ReviewWorkflow._format_files(
                "Importing files",
                context.importing_files,
            )
        )

        if context.truncated_sections:
            sections.append(
                "Truncated sections:\n"
                + "\n".join(
                    f"- {section}"
                    for section in context.truncated_sections
                )
            )

        return "\n\n".join(sections)

    @staticmethod
    def _format_symbols(title: str, symbols) -> str:
        lines = [f"{title}:"]

        if not symbols:
            lines.append("- None")
            return "\n".join(lines)

        for symbol in symbols:
            location = symbol.location
            lines.append(
                f"- {symbol.kind} {symbol.name} "
                f"({location.file_path}:"
                f"{location.start_line}-"
                f"{location.end_line})"
            )

        return "\n".join(lines)

    @staticmethod
    def _format_files(title: str, files) -> str:
        lines = [f"{title}:"]

        if not files:
            lines.append("- None")
            return "\n".join(lines)

        for file in files:
            lines.append(f"- {file.file_path}")

        return "\n".join(lines)