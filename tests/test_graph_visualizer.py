from pathlib import Path

from codelens.graph_queries import GraphRelationship
from codelens.graph_visualizer import GraphVisualizer


def test_render_creates_html_file(tmp_path: Path) -> None:
    relationships = [
        GraphRelationship(
            source_id="repo:a.py:run:1",
            source_name="run",
            source_kind="Function",
            relationship="CALLS",
            target_id="repo:b.py:process:4",
            target_name="process",
            target_kind="Function",
        )
    ]

    output_path = tmp_path / "graph.html"

    visualizer = GraphVisualizer()

    visualizer.render(
        relationships,
        output_path,
    )

    assert output_path.exists()

    html = output_path.read_text()

    assert "run" in html
    assert "process" in html
    assert "CALLS" in html