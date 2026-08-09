"""End-to-end CodeLens review workflow."""

from pathlib import Path
from typing import List, Optional

from .change_detector import ChangedSymbol, detect_changed_symbols
from .context_builder import ContextBuilder, ContextLimits
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
            context=str(context),
        )
