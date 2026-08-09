"""Deterministic prompt construction for CodeLens reviews."""

from .review import ReviewRequest


class PromptBuilder:
    """Build the review prompt sent to an LLM provider."""

    def build(self, request: ReviewRequest) -> str:
        """Return a deterministic review prompt for one changed symbol."""

        return (
            "You are reviewing a changed Python code symbol.\n\n"
            "Review only the supplied change and its relevant context. "
            "Identify concrete bugs, correctness issues, security problems, "
            "or maintainability problems that are directly supported by "
            "the provided evidence.\n\n"
            "Changed symbol:\n"
            f"- ID: {request.symbol_id}\n"
            f"- Name: {request.symbol_name}\n"
            f"- Type: {request.symbol_type}\n"
            f"- File: {request.file_path}\n"
            f"- Lines: {request.start_line}-{request.end_line}\n\n"
            "Source:\n"
            "```python\n"
            f"{request.source}\n"
            "```\n\n"
            "Graph context:\n"
            f"{request.context}\n\n"
            "Return only findings supported by the supplied source and "
            "context. Do not invent behavior or dependencies."
        )
