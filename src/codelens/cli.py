"""Command-line interface for CodeLens."""

import argparse
from pathlib import Path
import subprocess

from .analyzer import analyze_repository
from .gemini_provider import GeminiLLMProvider
from .graph_builder import GraphBuilder
from .graph_queries import GraphQueryService
from .graph_visualizer import GraphVisualizer
from .neo4j_client import Neo4jClient
from .review_workflow import ReviewWorkflow


def get_git_diff() -> str:
    """Return the current working-tree Git diff."""

    result = subprocess.run(
        ["git", "diff"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def index_repository(repository: Path) -> None:
    """Analyze and ingest the repository into Neo4j."""

    analyses = analyze_repository(repository)

    client = Neo4jClient()
    try:
        builder = GraphBuilder(client)
        builder.ingest(repository.resolve().name, analyses)
    finally:
        client.close()


def graph_repository(repository: Path) -> None:
    """Render the repository graph as an interactive HTML file."""

    client = Neo4jClient()

    try:
        graph_queries = GraphQueryService(client)
        relationships = graph_queries.relationships(
            repository.resolve().name,
        )

        output_path = repository / "codelens-graph.html"

        visualizer = GraphVisualizer()
        visualizer.render(
            relationships,
            output_path,
        )
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LLM-powered repository-aware code review."
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "index",
        help="Analyze and index the repository into Neo4j.",
    )

    subparsers.add_parser(
        "graph",
        help="Render the repository graph as an interactive HTML file.",
    )

    subparsers.add_parser(
        "review",
        help="Review current Git changes.",
    )

    args = parser.parse_args()

    if args.command == "index":
        index_repository(Path.cwd())
        print("Repository indexed.")
        return 0

    if args.command == "graph":
        graph_repository(Path.cwd())
        print("Graph written to codelens-graph.html.")
        return 0

    if args.command != "review":
        parser.print_help()
        return 1

    diff = get_git_diff()

    if not diff.strip():
        print("No changes to review.")
        return 0

    client = Neo4jClient()

    try:
        graph_queries = GraphQueryService(client)
        provider = GeminiLLMProvider()

        workflow = ReviewWorkflow(
            repository=Path.cwd(),
            graph_queries=graph_queries,
            provider=provider,
        )

        result = workflow.review(diff)
    finally:
        client.close()

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


if __name__ == "__main__":
    raise SystemExit(main())