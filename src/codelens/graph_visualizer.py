
"""Interactive HTML visualization of the CodeLens repository graph."""

from collections import Counter
from pathlib import Path
from typing import Iterable
import json

from pyvis.network import Network

from .graph_queries import GraphRelationship


NODE_COLORS = {
    "File": "#4C78A8",
    "Module": "#AB47BC",
    "Class": "#F58518",
    "Function": "#54A24B",
    "Method": "#E45756",
}

RELATIONSHIP_COLORS = {
    "CONTAINS": "#FFFFFF",
    "CALLS": "#00E676",
    "EXTENDS": "#FF9800",
    "IMPORTS": "#AB47BC",
}


class GraphVisualizer:
    """Render the CodeLens graph as a standalone interactive HTML file."""

    def render(
        self,
        relationships: Iterable[GraphRelationship],
        output_path: Path,
    ) -> None:
        relationships = list(relationships)

        network = Network(
            height="100vh",
            width="100%",
            directed=True,
            notebook=False,
            bgcolor="#000000",
            font_color="#FFFFFF",
        )

        nodes: dict[str, tuple[str, str]] = {}
        degrees: Counter[str] = Counter()

        for relationship in relationships:
            nodes[relationship.source_id] = (
                relationship.source_name,
                relationship.source_kind,
            )
            nodes[relationship.target_id] = (
                relationship.target_name,
                relationship.target_kind,
            )

            degrees[relationship.source_id] += 1
            degrees[relationship.target_id] += 1

        for node_id, (name, kind) in nodes.items():
            network.add_node(
                node_id,
                label=name,
                title=f"{kind}: {name}",
                color=NODE_COLORS.get(kind, "#777777"),
                font={"color": "#FFFFFF", "size": 16},
            )

        relationship_counts: Counter[str] = Counter()

        for edge_index, relationship in enumerate(relationships):
            relationship_counts[relationship.relationship] += 1
            color = RELATIONSHIP_COLORS.get(
                relationship.relationship,
                "#FFFFFF",
            )

            network.add_edge(
                relationship.source_id,
                relationship.target_id,
                id=edge_index,
                label=relationship.relationship,
                title=relationship.relationship,
                arrows="to",
                color=color,
                font={
                    "color": color,
                    "size": 12,
                    "strokeWidth": 0,
                },
            )

        network.set_options(
            """
            {
              "physics": {
                "enabled": true,
                "solver": "forceAtlas2Based",
                "forceAtlas2Based": {
                  "gravitationalConstant": -80,
                  "centralGravity": 0.005,
                  "springLength": 180,
                  "springConstant": 0.06,
                  "damping": 0.5,
                  "avoidOverlap": 1
                },
                "minVelocity": 0.75,
                "stabilization": {
                  "enabled": true,
                  "iterations": 500,
                  "updateInterval": 50
                }
              },
              "interaction": {
                "hover": true,
                "navigationButtons": false,
                "keyboard": true,
                "dragNodes": true,
                "dragView": true,
                "zoomView": true
              },
              "edges": {
                "smooth": {
                  "enabled": true,
                  "type": "dynamic"
                },
                "arrows": {
                  "to": {
                    "enabled": true,
                    "scaleFactor": 0.7
                  }
                }
              },
              "nodes": {
                "shape": "dot",
                "size": 22,
                "borderWidth": 2,
                "borderWidthSelected": 4
              }
            }
            """
        )

        html = network.generate_html()

        node_type_counts = Counter(
            kind for _, kind in nodes.values()
        )

        top_hubs = [
            {
                "id": node_id,
                "name": nodes[node_id][0],
                "kind": nodes[node_id][1],
                "degree": degree,
            }
            for node_id, degree in degrees.most_common(8)
        ]

        payload = {
            "nodes": [
                {
                    "id": node_id,
                    "name": name,
                    "kind": kind,
                }
                for node_id, (name, kind) in nodes.items()
            ],
            "relationships": [
                {
                    "source_id": relationship.source_id,
                    "source_name": relationship.source_name,
                    "source_kind": relationship.source_kind,
                    "relationship": relationship.relationship,
                    "target_id": relationship.target_id,
                    "target_name": relationship.target_name,
                    "target_kind": relationship.target_kind,
                }
                for relationship in relationships
            ],
        }

        panel = self._build_panel(
            node_type_counts=node_type_counts,
            relationship_counts=relationship_counts,
            top_hubs=top_hubs,
            total_nodes=len(nodes),
            total_relationships=len(relationships),
            payload=payload,
        )

        html = html.replace("</body>", panel + "</body>")

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        output_path.write_text(
            html,
            encoding="utf-8",
        )

    @staticmethod
    def _build_panel(
        *,
        node_type_counts: Counter[str],
        relationship_counts: Counter[str],
        top_hubs: list[dict],
        total_nodes: int,
        total_relationships: int,
        payload: dict,
    ) -> str:
        node_rows = ""
        for kind in (
            "File",
            "Module",
            "Class",
            "Function",
            "Method",
        ):
            count = node_type_counts.get(kind, 0)
            color = NODE_COLORS.get(kind, "#777777")
            node_rows += (
                '<label class="filter-row">'
                '<span class="filter-label">'
                f'<input type="checkbox" class="node-type-filter" '
                f'data-node-type="{kind}" checked>'
                f'<span class="legend-dot" '
                f'style="background:{color};"></span>'
                f'<span>{kind}</span>'
                '</span>'
                f'<strong>{count}</strong>'
                '</label>'
            )

        relationship_rows = ""
        for relationship in (
            "CONTAINS",
            "CALLS",
            "EXTENDS",
            "IMPORTS",
        ):
            count = relationship_counts.get(relationship, 0)
            color = RELATIONSHIP_COLORS.get(
                relationship,
                "#FFFFFF",
            )
            relationship_rows += (
                '<label class="filter-row">'
                '<span class="filter-label">'
                '<input type="checkbox" '
                'class="relationship-filter" '
                f'data-relationship="{relationship}" checked>'
                f'<span style="color:{color};">{relationship}</span>'
                '</span>'
                f'<strong>{count}</strong>'
                '</label>'
            )

        hub_rows = ""
        for index, hub in enumerate(top_hubs, start=1):
            color = NODE_COLORS.get(
                hub["kind"],
                "#777777",
            )
            hub_rows += (
                '<button class="hub-row" '
                f'data-hub-id="{hub["id"]}">'
                f'<span class="hub-rank">{index}</span>'
                f'<span class="legend-dot" '
                f'style="background:{color};"></span>'
                f'<span class="hub-name">{_escape_html(hub["name"])}</span>'
                f'<span class="hub-degree">{hub["degree"]}</span>'
                '</button>'
            )

        payload_json = json.dumps(
            payload,
            ensure_ascii=False,
        )

        panel = """
<style>
    :root {
        --panel: rgba(12, 12, 12, 0.95);
        --panel-border: #303030;
        --muted: #888888;
        --muted-2: #666666;
        --white: #FFFFFF;
        --green: #00E676;
    }

    #codelens-header {
        position: fixed;
        top: 18px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 999;
        display: flex;
        align-items: center;
        gap: 24px;
        padding: 10px 16px;
        border: 1px solid #292929;
        border-radius: 10px;
        background: rgba(10, 10, 10, 0.88);
        color: #FFFFFF;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        backdrop-filter: blur(8px);
        pointer-events: none;
    }

    #codelens-header-title {
        font-size: 16px;
        font-weight: 650;
        white-space: nowrap;
    }

    #codelens-header-subtitle {
        margin-left: 6px;
        color: #777777;
        font-size: 11px;
        font-weight: 400;
    }

    #codelens-legend {
        display: flex;
        align-items: center;
        gap: 12px;
        white-space: nowrap;
    }

    .legend-item {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        color: #AAAAAA;
        font-size: 10px;
    }

    .legend-dot {
        display: inline-block;
        width: 9px;
        height: 9px;
        border-radius: 50%;
        flex-shrink: 0;
    }

    .legend-line {
        width: 16px;
        height: 2px;
        display: inline-block;
        flex-shrink: 0;
    }

    #codelens-insights {
        position: fixed;
        top: 20px;
        left: 20px;
        width: 292px;
        max-height: calc(100vh - 40px);
        overflow-y: auto;
        z-index: 1000;
        box-sizing: border-box;
        padding: 18px;
        border: 1px solid var(--panel-border);
        border-radius: 12px;
        background: var(--panel);
        color: var(--white);
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.55);
        backdrop-filter: blur(8px);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        transition: width 0.2s ease, padding 0.2s ease;
    }

    #codelens-insights.collapsed {
        width: 52px;
        padding: 0;
        overflow: hidden;
    }

    #codelens-insights-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
    }

    #codelens-title {
        margin: 0;
        font-size: 18px;
        font-weight: 650;
        white-space: nowrap;
    }

    #codelens-toggle {
        flex-shrink: 0;
        width: 32px;
        height: 32px;
        padding: 0;
        border: 1px solid #333333;
        border-radius: 7px;
        background: #111111;
        color: #FFFFFF;
        cursor: pointer;
        font-size: 18px;
    }

    #codelens-toggle:hover,
    .filter-action:hover,
    #codelens-impact-close:hover {
        border-color: #555555;
        background: #1A1A1A;
    }

    #codelens-insights.collapsed #codelens-insights-content,
    #codelens-insights.collapsed #codelens-title {
        display: none;
    }

    #codelens-insights.collapsed #codelens-insights-header {
        height: 52px;
        justify-content: center;
    }

    .search-box {
        margin-top: 16px;
        border: 1px solid #333333;
        border-radius: 7px;
        background: #111111;
    }

    .search-box input {
        width: 100%;
        box-sizing: border-box;
        padding: 9px 10px;
        border: none;
        outline: none;
        background: transparent;
        color: #FFFFFF;
        font-size: 13px;
    }

    .search-box input::placeholder {
        color: #666666;
    }

    .search-results {
        margin-top: 8px;
        max-height: 220px;
        overflow-y: auto;
    }

    .search-result {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        width: 100%;
        margin-bottom: 2px;
        padding: 7px 8px;
        border: 1px solid transparent;
        border-radius: 6px;
        background: transparent;
        color: #FFFFFF;
        cursor: pointer;
        text-align: left;
        font-size: 12px;
    }

    .search-result:hover {
        background: #1A1A1A;
        border-color: #2E2E2E;
    }

    .search-result-content {
        min-width: 0;
        display: flex;
        align-items: center;
        gap: 7px;
    }

    .search-result-name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .search-result-kind {
        color: #777777;
        font-size: 10px;
        white-space: nowrap;
    }

    .search-result-actions {
        display: flex;
        gap: 4px;
        flex-shrink: 0;
    }

    .search-action {
        padding: 3px 6px;
        border: 1px solid #333333;
        border-radius: 4px;
        color: #999999;
        font-size: 10px;
    }

    .search-action:hover {
        border-color: #555555;
        color: #FFFFFF;
    }

    .summary {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin-top: 16px;
    }

    .summary-card {
        padding: 10px;
        border: 1px solid #2A2A2A;
        border-radius: 8px;
        background: #111111;
    }

    .summary-value {
        font-size: 20px;
        font-weight: 650;
    }

    .summary-label {
        margin-top: 3px;
        color: #888888;
        font-size: 11px;
    }

    .insight-section {
        margin-top: 18px;
    }

    .insight-section h3 {
        margin: 0 0 9px 0;
        color: #AAAAAA;
        font-size: 11px;
        font-weight: 650;
        letter-spacing: 0.08em;
    }

    .filter-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: 30px;
        cursor: pointer;
        font-size: 13px;
    }

    .filter-label {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .filter-row input {
        width: 14px;
        height: 14px;
        accent-color: var(--green);
        cursor: pointer;
    }

    .filter-row strong {
        color: #AAAAAA;
        font-weight: 500;
    }

    .filter-actions {
        display: flex;
        gap: 6px;
        margin-top: 8px;
    }

    .filter-action {
        flex: 1;
        padding: 6px 8px;
        border: 1px solid #333333;
        border-radius: 6px;
        background: #111111;
        color: #AAAAAA;
        cursor: pointer;
        font-size: 11px;
    }

    .hub-row {
        display: flex;
        align-items: center;
        width: 100%;
        gap: 7px;
        min-height: 30px;
        padding: 4px 0;
        border: 0;
        background: transparent;
        color: #FFFFFF;
        cursor: pointer;
        text-align: left;
        font-size: 12px;
    }

    .hub-row:hover {
        color: var(--green);
    }

    .hub-rank {
        width: 14px;
        color: #666666;
    }

    .hub-name {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .hub-degree {
        color: #AAAAAA;
        font-variant-numeric: tabular-nums;
    }

    .hint {
        margin-top: 18px;
        padding-top: 14px;
        border-top: 1px solid #2A2A2A;
        color: #777777;
        font-size: 11px;
        line-height: 1.5;
    }

    #codelens-impact {
        position: fixed;
        top: 20px;
        right: 20px;
        width: 340px;
        max-height: calc(100vh - 40px);
        overflow-y: auto;
        z-index: 1001;
        box-sizing: border-box;
        padding: 18px;
        border: 1px solid #333333;
        border-radius: 12px;
        background: var(--panel);
        color: #FFFFFF;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.55);
        backdrop-filter: blur(8px);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    .impact-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
    }

    .impact-title {
        font-size: 18px;
        font-weight: 650;
    }

    .impact-subtitle {
        margin-top: 3px;
        color: #888888;
        font-size: 12px;
    }

    #codelens-impact-close {
        width: 30px;
        height: 30px;
        padding: 0;
        border: 1px solid #333333;
        border-radius: 7px;
        background: #111111;
        color: #FFFFFF;
        cursor: pointer;
        font-size: 20px;
    }

    .impact-summary {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 7px;
        margin-top: 16px;
    }

    .impact-count {
        padding: 9px;
        border: 1px solid #292929;
        border-radius: 7px;
        background: #111111;
    }

    .impact-count-value {
        font-size: 17px;
        font-weight: 650;
    }

    .impact-count-label {
        margin-top: 2px;
        color: #777777;
        font-size: 10px;
    }

    .impact-section {
        margin-top: 18px;
    }

    .impact-section h3 {
        margin: 0 0 8px 0;
        color: #AAAAAA;
        font-size: 11px;
        font-weight: 650;
        letter-spacing: 0.08em;
    }

    .impact-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        min-height: 29px;
        padding: 3px 0;
        font-size: 12px;
    }

    .impact-name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .impact-kind {
        color: #777777;
        font-size: 10px;
        white-space: nowrap;
    }

    .impact-type {
        color: #888888;
        font-size: 10px;
        white-space: nowrap;
    }

    .impact-empty {
        color: #555555;
        font-size: 12px;
    }

    .impact-focus {
        margin-top: 16px;
        width: 100%;
        padding: 8px;
        border: 1px solid #333333;
        border-radius: 7px;
        background: #111111;
        color: #AAAAAA;
        cursor: pointer;
        font-size: 11px;
    }

    .impact-focus:hover {
        color: #FFFFFF;
        border-color: #555555;
    }

    @media (max-width: 900px) {
        #codelens-header {
            display: none;
        }

        #codelens-insights {
            width: 250px;
        }

        #codelens-impact {
            width: 280px;
        }
    }
</style>

<div id="codelens-header">
    <div id="codelens-header-title">
        CodeLens Graph Explorer
        <span id="codelens-header-subtitle">
            Repository Knowledge Graph
        </span>
    </div>

    <div id="codelens-legend">
        <span class="legend-item">
            <span class="legend-dot" style="background:#4C78A8;"></span>
            File
        </span>
        <span class="legend-item">
            <span class="legend-dot" style="background:#AB47BC;"></span>
            Module
        </span>
        <span class="legend-item">
            <span class="legend-dot" style="background:#F58518;"></span>
            Class
        </span>
        <span class="legend-item">
            <span class="legend-dot" style="background:#54A24B;"></span>
            Function
        </span>
        <span class="legend-item">
            <span class="legend-dot" style="background:#E45756;"></span>
            Method
        </span>
    </div>
</div>

<aside id="codelens-insights">
    <div id="codelens-insights-header">
        <h2 id="codelens-title">CodeLens Insights</h2>
        <button
            id="codelens-toggle"
            type="button"
            title="Collapse insights"
            aria-label="Collapse CodeLens Insights"
        >‹</button>
    </div>

    <div id="codelens-insights-content">
        <div class="search-box">
            <input
                id="codelens-search"
                type="search"
                placeholder="Search symbols..."
                autocomplete="off"
            >
        </div>

        <div
            id="codelens-search-results"
            class="search-results"
        ></div>

        <div class="summary">
            <div class="summary-card">
                <div class="summary-value">__TOTAL_NODES__</div>
                <div class="summary-label">Nodes</div>
            </div>
            <div class="summary-card">
                <div class="summary-value">__TOTAL_RELATIONSHIPS__</div>
                <div class="summary-label">Relationships</div>
            </div>
        </div>

        <div class="insight-section">
            <h3>Node Types</h3>
            __NODE_ROWS__

            <div class="filter-actions">
                <button
                    class="filter-action"
                    id="select-all-node-types"
                >Show all</button>
                <button
                    class="filter-action"
                    id="hide-all-node-types"
                >Hide all</button>
            </div>
        </div>

        <div class="insight-section">
            <h3>Relationships</h3>
            __RELATIONSHIP_ROWS__

            <div class="filter-actions">
                <button
                    class="filter-action"
                    id="select-all-relationships"
                >Show all</button>
                <button
                    class="filter-action"
                    id="hide-all-relationships"
                >Hide all</button>
            </div>
        </div>

        <div class="insight-section">
            <h3>Top Hubs</h3>
            __HUB_ROWS__
        </div>

        <div class="hint">
            Drag nodes to explore the graph.<br>
            Scroll to zoom.<br>
            Hover over nodes and edges for details.<br>
            Click a node to inspect its impact.
        </div>
    </div>
</aside>

<script>
    const codelensData = __PAYLOAD_JSON__;

    const codelensRelationshipTypes = new Set([
        "CONTAINS",
        "CALLS",
        "EXTENDS",
        "IMPORTS"
    ]);

    const codelensCallers = "CALLS";
    const codelensCallees = "CALLS";

    const insightsPanel =
        document.getElementById("codelens-insights");

    const insightsToggle =
        document.getElementById("codelens-toggle");

    insightsToggle.addEventListener("click", function() {
        const collapsed =
            insightsPanel.classList.toggle("collapsed");

        insightsToggle.textContent =
            collapsed ? "›" : "‹";

        insightsToggle.title =
            collapsed
                ? "Expand insights"
                : "Collapse insights";

        insightsToggle.setAttribute(
            "aria-label",
            collapsed
                ? "Expand CodeLens Insights"
                : "Collapse CodeLens Insights"
        );
    });

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function nodeById(nodeId) {
        return codelensData.nodes.find(
            node => node.id === nodeId
        );
    }

    function focusGraphNode(nodeId) {
        if (
            typeof network === "undefined" ||
            typeof nodes === "undefined"
        ) {
            return;
        }

        const node = nodeById(nodeId);

        if (!node) {
            return;
        }

        network.selectNodes([nodeId]);

        network.focus(
            nodeId,
            {
                scale: 1.5,
                animation: {
                    duration: 600,
                    easingFunction: "easeInOutQuad"
                }
            }
        );
    }

    function selectedRelationshipTypes() {
        return new Set(
            Array.from(
                document.querySelectorAll(
                    ".relationship-filter:checked"
                )
            ).map(
                checkbox =>
                    checkbox.dataset.relationship
            )
        );
    }

    function selectedNodeTypes() {
        return new Set(
            Array.from(
                document.querySelectorAll(
                    ".node-type-filter:checked"
                )
            ).map(
                checkbox =>
                    checkbox.dataset.nodeType
            )
        );
    }

    function updateGraphVisibility() {
        if (
            typeof nodes === "undefined" ||
            typeof edges === "undefined"
        ) {
            return;
        }

        const visibleTypes =
            selectedNodeTypes();

        const visibleRelationships =
            selectedRelationshipTypes();

        const visibleNodeIds = new Set();

        codelensData.nodes.forEach(function(node) {
            if (visibleTypes.has(node.kind)) {
                visibleNodeIds.add(node.id);
            }
        });

        nodes.update(
            codelensData.nodes.map(function(node) {
                return {
                    id: node.id,
                    hidden:
                        !visibleTypes.has(node.kind)
                };
            })
        );

        edges.update(
            codelensData.relationships.map(
                function(relationship, index) {
                    return {
                        id: index,
                        hidden:
                            !visibleRelationships.has(
                                relationship.relationship
                            ) ||
                            !visibleNodeIds.has(
                                relationship.source_id
                            ) ||
                            !visibleNodeIds.has(
                                relationship.target_id
                            )
                    };
                }
            )
        );
    }

    function relationshipRowsFor(
        nodeId,
        direction,
        relationshipType
    ) {
        return codelensData.relationships.filter(
            function(relationship) {
                const directionMatches =
                    direction === "incoming"
                        ? relationship.target_id === nodeId
                        : relationship.source_id === nodeId;

                return (
                    directionMatches &&
                    relationship.relationship ===
                        relationshipType
                );
            }
        );
    }

    function renderImpactRows(
        relationships,
        direction
    ) {
        if (!relationships.length) {
            return (
                '<div class="impact-empty">' +
                "None" +
                "</div>"
            );
        }

        return relationships
            .map(function(relationship) {
                const relatedId =
                    direction === "incoming"
                        ? relationship.source_id
                        : relationship.target_id;

                const relatedNode =
                    nodeById(relatedId);

                const name =
                    relatedNode
                        ? relatedNode.name
                        : relatedId;

                const kind =
                    relatedNode
                        ? relatedNode.kind
                        : "";

                return (
                    '<div class="impact-row">' +
                    '<span class="impact-name">' +
                    escapeHtml(name) +
                    "</span>" +
                    '<span class="impact-kind">' +
                    escapeHtml(kind) +
                    "</span>" +
                    "</div>"
                );
            })
            .join("");
    }

    function renderTypedSection(
        title,
        relationships,
        direction
    ) {
        if (!relationships.length) {
            return "";
        }

        return (
            '<div class="impact-section">' +
            "<h3>" +
            escapeHtml(title) +
            "</h3>" +
            renderImpactRows(
                relationships,
                direction
            ) +
            "</div>"
        );
    }

    function showNodeImpact(nodeId) {
        const node = nodeById(nodeId);

        if (!node) {
            return;
        }

        const callers =
            relationshipRowsFor(
                nodeId,
                "incoming",
                codelensCallers
            );

        const callees =
            relationshipRowsFor(
                nodeId,
                "outgoing",
                codelensCallees
            );

        const incomingExtends =
            relationshipRowsFor(
                nodeId,
                "incoming",
                "EXTENDS"
            );

        const outgoingExtends =
            relationshipRowsFor(
                nodeId,
                "outgoing",
                "EXTENDS"
            );

        const incomingContains =
            relationshipRowsFor(
                nodeId,
                "incoming",
                "CONTAINS"
            );

        const outgoingContains =
            relationshipRowsFor(
                nodeId,
                "outgoing",
                "CONTAINS"
            );

        const incomingImports =
            relationshipRowsFor(
                nodeId,
                "incoming",
                "IMPORTS"
            );

        const outgoingImports =
            relationshipRowsFor(
                nodeId,
                "outgoing",
                "IMPORTS"
            );

        const oldPanel =
            document.getElementById(
                "codelens-impact"
            );

        if (oldPanel) {
            oldPanel.remove();
        }

        const impact =
            document.createElement("aside");

        impact.id = "codelens-impact";

        const totalImpact =
            callers.length +
            callees.length +
            incomingExtends.length +
            outgoingExtends.length;

        impact.innerHTML =
            '<div class="impact-header">' +
                "<div>" +
                    '<div class="impact-title">' +
                        escapeHtml(node.name) +
                    "</div>" +
                    '<div class="impact-subtitle">' +
                        escapeHtml(node.kind) +
                    "</div>" +
                "</div>" +
                '<button id="codelens-impact-close" ' +
                    'type="button" ' +
                    'aria-label="Close impact">' +
                    "×" +
                "</button>" +
            "</div>" +

            '<div class="impact-summary">' +
                '<div class="impact-count">' +
                    '<div class="impact-count-value">' +
                        callers.length +
                    "</div>" +
                    '<div class="impact-count-label">' +
                        "Callers" +
                    "</div>" +
                "</div>" +

                '<div class="impact-count">' +
                    '<div class="impact-count-value">' +
                        callees.length +
                    "</div>" +
                    '<div class="impact-count-label">' +
                        "Callees" +
                    "</div>" +
                "</div>" +

                '<div class="impact-count">' +
                    '<div class="impact-count-value">' +
                        incomingExtends.length +
                        outgoingExtends.length +
                    "</div>" +
                    '<div class="impact-count-label">' +
                        "Inheritance" +
                    "</div>" +
                "</div>" +

                '<div class="impact-count">' +
                    '<div class="impact-count-value">' +
                        totalImpact +
                    "</div>" +
                    '<div class="impact-count-label">' +
                        "Direct impact" +
                    "</div>" +
                "</div>" +
            "</div>" +

            '<div class="impact-section">' +
                "<h3>CALLERS</h3>" +
                renderImpactRows(
                    callers,
                    "incoming"
                ) +
            "</div>" +

            '<div class="impact-section">' +
                "<h3>CALLEES</h3>" +
                renderImpactRows(
                    callees,
                    "outgoing"
                ) +
            "</div>" +

            renderTypedSection(
                "SUBCLASSES",
                outgoingExtends,
                "outgoing"
            ) +

            renderTypedSection(
                "BASE CLASSES",
                incomingExtends,
                "incoming"
            ) +

            renderTypedSection(
                "CONTAINS",
                outgoingContains,
                "outgoing"
            ) +

            renderTypedSection(
                "CONTAINED BY",
                incomingContains,
                "incoming"
            ) +

            renderTypedSection(
                "IMPORTS",
                outgoingImports,
                "outgoing"
            ) +

            renderTypedSection(
                "IMPORTED BY",
                incomingImports,
                "incoming"
            ) +

            '<button class="impact-focus" ' +
                'id="codelens-impact-focus">' +
                "Focus in graph" +
            "</button>";

        document.body.appendChild(impact);

        document
            .getElementById(
                "codelens-impact-close"
            )
            .addEventListener(
                "click",
                function() {
                    impact.remove();
                }
            );

        document
            .getElementById(
                "codelens-impact-focus"
            )
            .addEventListener(
                "click",
                function() {
                    focusGraphNode(nodeId);
                }
            );

        focusGraphNode(nodeId);
    }

    function renderSearchResults(query) {
        const container =
            document.getElementById(
                "codelens-search-results"
            );

        container.innerHTML = "";

        const normalized =
            query.trim().toLowerCase();

        if (!normalized) {
            return;
        }

        const matches =
            codelensData.nodes
                .filter(function(node) {
                    return node.name
                        .toLowerCase()
                        .includes(normalized);
                })
                .slice(0, 12);

        matches.forEach(function(node) {
            const button =
                document.createElement("button");

            button.className =
                "search-result";

            button.innerHTML =
                '<span class="search-result-content">' +
                    '<span class="search-result-name">' +
                        escapeHtml(node.name) +
                    "</span>" +
                    '<span class="search-result-kind">' +
                        escapeHtml(node.kind) +
                    "</span>" +
                "</span>" +

                '<span class="search-result-actions">' +
                    '<span class="search-action" ' +
                        'data-action="focus">' +
                        "Focus" +
                    "</span>" +
                    '<span class="search-action" ' +
                        'data-action="impact">' +
                        "Impact" +
                    "</span>" +
                "</span>";

            button
                .querySelector(
                    '[data-action="focus"]'
                )
                .addEventListener(
                    "click",
                    function(event) {
                        event.stopPropagation();
                        focusGraphNode(node.id);
                    }
                );

            button
                .querySelector(
                    '[data-action="impact"]'
                )
                .addEventListener(
                    "click",
                    function(event) {
                        event.stopPropagation();
                        showNodeImpact(node.id);
                    }
                );

            button.addEventListener(
                "click",
                function() {
                    focusGraphNode(node.id);
                }
            );

            container.appendChild(button);
        });
    }

    document
        .getElementById("codelens-search")
        .addEventListener(
            "input",
            function(event) {
                renderSearchResults(
                    event.target.value
                );
            }
        );

    document
        .querySelectorAll(".relationship-filter")
        .forEach(function(checkbox) {
            checkbox.addEventListener(
                "change",
                updateGraphVisibility
            );
        });

    document
        .querySelectorAll(".node-type-filter")
        .forEach(function(checkbox) {
            checkbox.addEventListener(
                "change",
                updateGraphVisibility
            );
        });

    document
        .getElementById("select-all-relationships")
        .addEventListener(
            "click",
            function() {
                document
                    .querySelectorAll(
                        ".relationship-filter"
                    )
                    .forEach(function(checkbox) {
                        checkbox.checked = true;
                    });

                updateGraphVisibility();
            }
        );

    document
        .getElementById("hide-all-relationships")
        .addEventListener(
            "click",
            function() {
                document
                    .querySelectorAll(
                        ".relationship-filter"
                    )
                    .forEach(function(checkbox) {
                        checkbox.checked = false;
                    });

                updateGraphVisibility();
            }
        );

    document
        .getElementById("select-all-node-types")
        .addEventListener(
            "click",
            function() {
                document
                    .querySelectorAll(
                        ".node-type-filter"
                    )
                    .forEach(function(checkbox) {
                        checkbox.checked = true;
                    });

                updateGraphVisibility();
            }
        );

    document
        .getElementById("hide-all-node-types")
        .addEventListener(
            "click",
            function() {
                document
                    .querySelectorAll(
                        ".node-type-filter"
                    )
                    .forEach(function(checkbox) {
                        checkbox.checked = false;
                    });

                updateGraphVisibility();
            }
        );

    document
        .querySelectorAll(".hub-row")
        .forEach(function(button) {
            button.addEventListener(
                "click",
                function() {
                    const nodeId =
                        button.dataset.hubId;

                    showNodeImpact(nodeId);
                }
            );
        });

    if (
        typeof network !== "undefined"
    ) {
        network.on(
            "click",
            function(properties) {
                const nodeIds =
                    properties.nodes || [];

                if (nodeIds.length !== 1) {
                    return;
                }

                showNodeImpact(
                    nodeIds[0]
                );
            }
        );
    }
</script>
"""

        panel = panel.replace(
        "__TOTAL_NODES__",
        str(total_nodes),
    ).replace(
        "__TOTAL_RELATIONSHIPS__",
        str(total_relationships),
    ).replace(
        "__NODE_ROWS__",
        node_rows,
    ).replace(
        "__RELATIONSHIP_ROWS__",
        relationship_rows,
    ).replace(
        "__HUB_ROWS__",
        hub_rows,
    ).replace(
        "__PAYLOAD_JSON__",
        payload_json,
    )

        return panel


def _escape_html(value: object) -> str:
    """Escape text inserted into generated HTML."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )
