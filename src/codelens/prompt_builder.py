"""Build prompts for CodeLens review requests."""

from .review import ReviewRequest


class PromptBuilder:
    """Build deterministic prompts for repository-aware code reviews."""

    def build(self, request: ReviewRequest) -> str:
        """Build the review prompt for one changed symbol."""

        changed_lines = self._format_changed_lines(request)

        return (
            "You are reviewing a code change in a Python repository.\n\n"
            "Review only the supplied change and its relevant context. "
            "Identify concrete correctness, reliability, maintainability, "
            "or security problems introduced by the change. "
            "Do not invent behavior or dependencies.\n\n"
            "Symbol ID:\n"
            f"{request.symbol_id}\n\n"
            "File:\n"
            f"{request.file_path}\n\n"
            "Symbol:\n"
            f"{request.symbol_type} {request.symbol_name}\n"
            f"Lines: {request.start_line}-{request.end_line}\n\n"
            "Changed lines:\n"
            f"{changed_lines}\n\n"
            "Source:\n"
            "```python\n"
            f"{request.source}\n"
            "```\n\n"
            "Graph context:\n"
            f"{request.context}\n\n"
            "Return findings as the required JSON object."
        )

    @staticmethod
    def _format_changed_lines(request: ReviewRequest) -> str:
        """Format the exact new-file ranges touched by the change."""

        if not request.changed_ranges:
            return "- None"

        return "\n".join(
            f"- {changed.start_line}-{changed.end_line}"
            for changed in request.changed_ranges
        )