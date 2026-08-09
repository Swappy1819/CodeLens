"""Command-line interface for CodeLens."""

import argparse
import subprocess
from pathlib import Path

from .gemini_provider import GeminiLLMProvider
from .graph_queries import GraphQueryService
from .neo4j_client import Neo4jClient
from .review_workflow import ReviewWorkflow


def get_git_diff() -> str:
    """Return the current working-tree Git diff."""

    result = subprocess.run(
        ["git", "diff"],
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout


def main() -> int:
    """Run the CodeLens command-line interface."""

    parser = argparse.ArgumentParser(
        prog="codelens",
        description="LLM-powered repository-aware code review.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "review",
        help="Review the current Git changes.",
    )

    args = parser.parse_args()

    if args.command != "review":
        return 1

    diff = get_git_diff()

    if not diff.strip():
        print("No changes to review.")
        return 0

    client = Neo4jClient()

    try:
        client.verify_connection()

        graph_queries = GraphQueryService(client)
        provider = GeminiLLMProvider()

        workflow = ReviewWorkflow(
            repository=Path.cwd(),
            graph_queries=graph_queries,
            provider=provider,
        )

        result = workflow.review(diff)

        if not result.findings:
            print("No review findings.")
            return 0

        for finding in result.findings:
            print(
                f"[{finding.severity.upper()}] "
                f"{finding.title}"
            )
            print(
                f"{finding.file_path}:"
                f"{finding.start_line}-"
                f"{finding.end_line}"
            )
            print(finding.description)
            print()

        return 0

    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())