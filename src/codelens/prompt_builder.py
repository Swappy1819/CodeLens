"""Build prompts for CodeLens review requests."""

from .review import ReviewRequest


class PromptBuilder:
    """Build deterministic prompts for repository-aware code reviews."""

    def build(self, request: ReviewRequest) -> str:
        """Build the review prompt for one changed symbol."""

        changed_lines = self._format_changed_lines(request)

        return (
            "You are reviewing a code change in a Python repository.\n\n"
            "Review ONLY the supplied change and its directly relevant "
            "repository context.\n\n"
            "STRICT REVIEW SCOPE:\n"
            "- Report only problems introduced by the supplied change.\n"
            "- A finding must be directly supported by the changed lines, "
            "the supplied source, or verified repository context.\n"
            "- Do not report pre-existing problems.\n"
            "- Do not report problems from unrelated files or symbols.\n"
            "- Do not report speculative problems.\n"
            "- Do not claim a function, class, method, or module is undefined "
            "if its definition is present in the supplied source or verified "
            "repository context.\n"
            "- If the supplied source shows that a symbol is defined, treat "
            "that definition as authoritative.\n"
            "- Symbols listed in Graph context are verified repository "
            "symbols. Do not report a symbol as undefined when it appears "
            "in Graph context.\n"
            "- If you cannot establish that a problem was introduced by the "
            "change, do not report it.\n\n"
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