"""Interactive HTML visualization of the CodeLens graph."""

from collections import Counter
from pathlib import Path
from typing import Iterable

from pyvis.network import Network

from .graph_queries import GraphRelationship


NODE_COLORS = {
    "File": "#4C78A8",
    "Class": "#F58518",
    "Function": "#54A24B",
    "Method": "#E45756",
    "Module": "#B279A2",
}

RELATIONSHIP_COLORS = {
    "CONTAINS": "#FFFFFF",
    "CALLS": "#00E676",
    "EXTENDS": "#FF9800",
    "IMPORTS": "#AB47BC",
}


class GraphVisualizer:
    """Render CodeLens graph relationships as an interactive HTML graph."""

    def render(
        self,
        relationships: Iterable[GraphRelationship],
        output_path: Path,
    ) -> None:
        """Render relationships to a standalone HTML file."""

        network = Network(
            height="100vh",
            width="100%",
            directed=True,
            notebook=False,
            bgcolor="#000000",
            font_color="#FFFFFF",
        )

        relationships = list(relationships)

        nodes = {}

        for relationship in relationships:
            nodes[relationship.source_id] = (
                relationship.source_name,
                relationship.source_kind,
            )
            nodes[relationship.target_id] = (
                relationship.target_name,
                relationship.target_kind,
            )

        for node_id, (name, kind) in nodes.items():
            network.add_node(
                node_id,
                label=name,
                title=f"{kind}: {name}",
                color=NODE_COLORS.get(kind, "#777777"),
                font={
                    "color": "#FFFFFF",
                    "size": 16,
                },
            )

        relationship_counts = Counter()
        node_degrees = Counter()

        for relationship in relationships:
            relationship_color = RELATIONSHIP_COLORS.get(
                relationship.relationship,
                "#FFFFFF",
            )

            relationship_counts[relationship.relationship] += 1
            node_degrees[relationship.source_id] += 1
            node_degrees[relationship.target_id] += 1

            network.add_edge(
                relationship.source_id,
                relationship.target_id,
                label=relationship.relationship,
                title=relationship.relationship,
                arrows="to",
                color=relationship_color,
                font={
                    "color": relationship_color,
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
                "borderWidthSelected": 3
              }
            }
            """
        )

        html = network.generate_html()

        insights = self._build_insights(
            nodes,
            relationships,
            relationship_counts,
            node_degrees,
        )

        html = self._inject_insights(html, insights)

        output_path.write_text(
            html,
            encoding="utf-8",
        )

    @staticmethod
    def _build_insights(
        nodes,
        relationships,
        relationship_counts,
        node_degrees,
    ) -> dict:
        """Build repository statistics for the graph insights panel."""

        node_type_counts = Counter(
            kind
            for _, (_, kind) in nodes.items()
        )

        node_lookup = {
            node_id: (name, kind)
            for node_id, (name, kind) in nodes.items()
        }

        top_hubs = []

        for node_id, degree in node_degrees.most_common(5):
            name, kind = node_lookup[node_id]

            top_hubs.append(
                {
                    "name": name,
                    "kind": kind,
                    "degree": degree,
                }
            )

        return {
            "total_nodes": len(nodes),
            "total_relationships": len(relationships),
            "node_type_counts": node_type_counts,
            "relationship_counts": relationship_counts,
            "top_hubs": top_hubs,
        }

    @staticmethod
    def _inject_insights(
        html: str,
        insights: dict,
    ) -> str:
        """Inject the expandable CodeLens Insights panel."""

        node_type_rows = ""

        for kind in (
            "File",
            "Class",
            "Function",
            "Method",
            "Module",
        ):
            count = insights["node_type_counts"].get(kind, 0)
            color = NODE_COLORS.get(kind, "#FFFFFF")

            node_type_rows += f"""
                <label class="filter-row">
                    <span>
                        <input
                            type="checkbox"
                            class="node-type-filter"
                            data-node-type="{kind}"
                            checked
                        >
                        <span
                            class="legend-dot"
                            style="background:{color};"
                        ></span>
                        <span class="node-type-name">
                            {kind}
                        </span>
                    </span>
                    <strong>{count}</strong>
                </label>
            """

        relationship_rows = ""

        for relationship, count in sorted(
            insights["relationship_counts"].items(),
            key=lambda item: (-item[1], item[0]),
        ):
            color = RELATIONSHIP_COLORS.get(
                relationship,
                "#FFFFFF",
            )

            relationship_rows += f"""
                <label class="filter-row">
                    <span>
                        <input
                            type="checkbox"
                            class="relationship-filter"
                            data-relationship="{relationship}"
                            checked
                        >
                        <span
                            class="relationship-name"
                            style="color:{color};"
                        >
                            {relationship}
                        </span>
                    </span>
                    <strong>{count}</strong>
                </label>
            """

        hub_rows = ""

        for index, hub in enumerate(
            insights["top_hubs"],
            start=1,
        ):
            color = NODE_COLORS.get(
                hub["kind"],
                "#FFFFFF",
            )

            hub_rows += f"""
                <div class="hub-row">
                    <span class="hub-rank">{index}</span>
                    <span
                        class="legend-dot"
                        style="background:{color};"
                    ></span>
                    <span class="hub-name">
                        {hub["name"]}
                    </span>
                    <span class="hub-degree">
                        {hub["degree"]}
                    </span>
                </div>
            """

        panel = f"""
        <style>
            #codelens-insights {{
                position: fixed;
                top: 20px;
                left: 20px;
                width: 290px;
                max-height: calc(100vh - 40px);
                overflow-y: auto;
                z-index: 1000;
                box-sizing: border-box;
                padding: 18px;
                border: 1px solid #333333;
                border-radius: 12px;
                background: rgba(12, 12, 12, 0.94);
                color: #FFFFFF;
                box-shadow:
                    0 10px 40px rgba(0, 0, 0, 0.55);
                backdrop-filter: blur(8px);
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    sans-serif;
                transition:
                    width 0.2s ease,
                    padding 0.2s ease;
            }}

            #codelens-insights.collapsed {{
                width: 52px;
                padding: 0;
                overflow: hidden;
            }}

            #codelens-insights-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
            }}

            #codelens-insights h2 {{
                margin: 0;
                font-size: 18px;
                font-weight: 600;
                white-space: nowrap;
            }}

            #codelens-toggle {{
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
                line-height: 1;
            }}

            #codelens-toggle:hover {{
                border-color: #555555;
                background: #1A1A1A;
            }}

            #codelens-insights.collapsed
            #codelens-insights-content {{
                display: none;
            }}

            #codelens-insights.collapsed
            #codelens-insights-header {{
                height: 52px;
                justify-content: center;
            }}

            #codelens-insights.collapsed
            #codelens-toggle {{
                width: 34px;
                height: 34px;
            }}

            #codelens-insights.collapsed
            #codelens-title {{
                display: none;
            }}

            .search-box {{
                display: flex;
                align-items: center;
                margin-top: 16px;
                border: 1px solid #333333;
                border-radius: 7px;
                background: #111111;
            }}

            .search-box input {{
                width: 100%;
                padding: 9px 10px;
                border: none;
                outline: none;
                background: transparent;
                color: #FFFFFF;
                font-size: 13px;
            }}

            .search-box input::placeholder {{
                color: #666666;
            }}

            .search-results {{
                margin-top: 8px;
                max-height: 180px;
                overflow-y: auto;
            }}

            .search-result {{
                display: flex;
                align-items: center;
                gap: 8px;
                width: 100%;
                padding: 7px 8px;
                border: none;
                border-radius: 5px;
                background: transparent;
                color: #FFFFFF;
                cursor: pointer;
                text-align: left;
                font-size: 12px;
            }}

            .search-result:hover {{
                background: #1A1A1A;
            }}

            .search-result-kind {{
                color: #777777;
                font-size: 10px;
            }}

            .insight-section {{
                margin-top: 18px;
            }}

            .insight-section h3 {{
                margin: 0 0 10px 0;
                color: #AAAAAA;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.08em;
            }}

            .summary {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
                margin-top: 16px;
            }}

            .summary-card {{
                padding: 10px;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                background: #111111;
            }}

            .summary-value {{
                font-size: 20px;
                font-weight: 600;
            }}

            .summary-label {{
                margin-top: 3px;
                color: #888888;
                font-size: 11px;
            }}

            .insight-row {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                min-height: 26px;
                font-size: 13px;
            }}

            .filter-row {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                min-height: 30px;
                cursor: pointer;
                font-size: 13px;
            }}

            .filter-row span:first-child {{
                display: flex;
                align-items: center;
                gap: 8px;
            }}

            .filter-row input {{
                width: 14px;
                height: 14px;
                accent-color: #00E676;
                cursor: pointer;
            }}

            .filter-row strong {{
                color: #AAAAAA;
                font-weight: 500;
            }}

            .relationship-name {{
                font-weight: 500;
            }}

            .node-type-name {{
                font-weight: 500;
            }}

            .legend-dot {{
                display: inline-block;
                width: 9px;
                height: 9px;
                border-radius: 50%;
                flex-shrink: 0;
            }}

            .hub-row {{
                display: flex;
                align-items: center;
                gap: 7px;
                min-height: 30px;
                font-size: 12px;
            }}

            .hub-rank {{
                width: 14px;
                color: #666666;
            }}

            .hub-name {{
                flex: 1;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}

            .hub-degree {{
                color: #AAAAAA;
                font-variant-numeric: tabular-nums;
            }}

            .hint {{
                margin-top: 18px;
                padding-top: 14px;
                border-top: 1px solid #2A2A2A;
                color: #777777;
                font-size: 11px;
                line-height: 1.5;
            }}

            .filter-actions {{
                display: flex;
                gap: 6px;
                margin-top: 8px;
            }}

            .filter-action {{
                flex: 1;
                padding: 6px 8px;
                border: 1px solid #333333;
                border-radius: 6px;
                background: #111111;
                color: #AAAAAA;
                cursor: pointer;
                font-size: 11px;
            }}

            .filter-action:hover {{
                border-color: #555555;
                color: #FFFFFF;
            }}
        </style>

        <aside id="codelens-insights">
            <div id="codelens-insights-header">
                <h2 id="codelens-title">
                    CodeLens Insights
                </h2>

                <button
                    id="codelens-toggle"
                    type="button"
                    aria-label="Collapse CodeLens Insights"
                    title="Collapse insights"
                >
                    ‹
                </button>
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
                        <div class="summary-value">
                            {insights["total_nodes"]}
                        </div>
                        <div class="summary-label">
                            Nodes
                        </div>
                    </div>

                    <div class="summary-card">
                        <div class="summary-value">
                            {insights["total_relationships"]}
                        </div>
                        <div class="summary-label">
                            Relationships
                        </div>
                    </div>
                </div>

                <div class="insight-section">
                    <h3>Node Types</h3>
                    {node_type_rows}

                    <div class="filter-actions">
                        <button
                            class="filter-action"
                            id="select-all-node-types"
                        >
                            Show all
                        </button>

                        <button
                            class="filter-action"
                            id="hide-all-node-types"
                        >
                            Hide all
                        </button>
                    </div>
                </div>

                <div class="insight-section">
                    <h3>Relationships</h3>
                    {relationship_rows}

                    <div class="filter-actions">
                        <button
                            class="filter-action"
                            id="select-all-relationships"
                        >
                            Show all
                        </button>

                        <button
                            class="filter-action"
                            id="hide-all-relationships"
                        >
                            Hide all
                        </button>
                    </div>
                </div>

                <div class="insight-section">
                    <h3>Top Hubs</h3>
                    {hub_rows}
                </div>

                <div class="hint">
                    Drag nodes to explore the graph.<br>
                    Scroll to zoom.<br>
                    Hover over nodes and edges for details.
                </div>
            </div>
        </aside>

        <script>
            const insightsPanel =
                document.getElementById(
                    "codelens-insights"
                );

            const insightsToggle =
                document.getElementById(
                    "codelens-toggle"
                );

            insightsToggle.addEventListener(
                "click",
                function() {{
                    const collapsed =
                        insightsPanel.classList.toggle(
                            "collapsed"
                        );

                    if (collapsed) {{
                        insightsToggle.textContent = "›";
                        insightsToggle.title =
                            "Expand insights";
                        insightsToggle.setAttribute(
                            "aria-label",
                            "Expand CodeLens Insights"
                        );
                    }} else {{
                        insightsToggle.textContent = "‹";
                        insightsToggle.title =
                            "Collapse insights";
                        insightsToggle.setAttribute(
                            "aria-label",
                            "Collapse CodeLens Insights"
                        );
                    }}
                }}
            );

            function getSelectedRelationships() {{
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
            }}

            function getSelectedNodeTypes() {{
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
            }}

            function updateGraphVisibility() {{
                if (
                    typeof edges === "undefined" ||
                    typeof nodes === "undefined"
                ) {{
                    return;
                }}

                const selectedRelationships =
                    getSelectedRelationships();

                const selectedNodeTypes =
                    getSelectedNodeTypes();

                const visibleNodes = new Set();

                nodes.forEach(function(node) {{
                    const nodeType =
                        getNodeType(node.title);

                    const visible =
                        selectedNodeTypes.has(nodeType);

                    if (visible) {{
                        visibleNodes.add(node.id);
                    }}
                }});

                const nodeUpdates = [];

                nodes.forEach(function(node) {{
                    const nodeType =
                        getNodeType(node.title);

                    nodeUpdates.push({{
                        id: node.id,
                        hidden:
                            !selectedNodeTypes.has(
                                nodeType
                            )
                    }});
                }});

                nodes.update(nodeUpdates);

                const edgeUpdates = [];

                edges.forEach(function(edge) {{
                    const relationship =
                        edge.label || "";

                    const sourceVisible =
                        visibleNodes.has(edge.from);

                    const targetVisible =
                        visibleNodes.has(edge.to);

                    edgeUpdates.push({{
                        id: edge.id,
                        hidden:
                            !selectedRelationships.has(
                                relationship
                            ) ||
                            !sourceVisible ||
                            !targetVisible
                    }});
                }});

                edges.update(edgeUpdates);
            }}

            function getNodeType(title) {{
                if (!title) {{
                    return "";
                }}

                const separator =
                    title.indexOf(":");

                if (separator === -1) {{
                    return "";
                }}

                return title
                    .substring(0, separator)
                    .trim();
            }}

            document
                .querySelectorAll(".relationship-filter")
                .forEach(function(checkbox) {{
                    checkbox.addEventListener(
                        "change",
                        updateGraphVisibility
                    );
                }});

            document
                .querySelectorAll(".node-type-filter")
                .forEach(function(checkbox) {{
                    checkbox.addEventListener(
                        "change",
                        updateGraphVisibility
                    );
                }});

            document
                .getElementById("select-all-relationships")
                .addEventListener(
                    "click",
                    function() {{
                        document
                            .querySelectorAll(
                                ".relationship-filter"
                            )
                            .forEach(function(checkbox) {{
                                checkbox.checked = true;
                            }});

                        updateGraphVisibility();
                    }}
                );

            document
                .getElementById("hide-all-relationships")
                .addEventListener(
                    "click",
                    function() {{
                        document
                            .querySelectorAll(
                                ".relationship-filter"
                            )
                            .forEach(function(checkbox) {{
                                checkbox.checked = false;
                            }});

                        updateGraphVisibility();
                    }}
                );

            document
                .getElementById("select-all-node-types")
                .addEventListener(
                    "click",
                    function() {{
                        document
                            .querySelectorAll(
                                ".node-type-filter"
                            )
                            .forEach(function(checkbox) {{
                                checkbox.checked = true;
                            }});

                        updateGraphVisibility();
                    }}
                );

            document
                .getElementById("hide-all-node-types")
                .addEventListener(
                    "click",
                    function() {{
                        document
                            .querySelectorAll(
                                ".node-type-filter"
                            )
                            .forEach(function(checkbox) {{
                                checkbox.checked = false;
                            }});

                        updateGraphVisibility();
                    }}
                );

            const codelensNodes = [];

            nodes.forEach(function(node) {{
                codelensNodes.push({{
                    id: node.id,
                    label: node.label || "",
                    title: node.title || "",
                }});
            }});

            const searchInput =
                document.getElementById(
                    "codelens-search"
                );

            const searchResults =
                document.getElementById(
                    "codelens-search-results"
                );

            function renderSearchResults(query) {{
                searchResults.innerHTML = "";

                const normalizedQuery =
                    query.trim().toLowerCase();

                if (!normalizedQuery) {{
                    return;
                }}

                const matches = codelensNodes
                    .filter(function(node) {{
                        return (
                            node.label
                                .toLowerCase()
                                .includes(normalizedQuery)
                        );
                    }})
                    .slice(0, 10);

                matches.forEach(function(node) {{
                    const button =
                        document.createElement(
                            "button"
                        );

                    button.className =
                        "search-result";

                    button.innerHTML = `
                        <span>${{node.label}}</span>
                        <span class="search-result-kind">
                            ${{node.title}}
                        </span>
                    `;

                    button.addEventListener(
                        "click",
                        function() {{
                            focusGraphNode(node.id);
                        }}
                    );

                    searchResults.appendChild(
                        button
                    );
                }});
            }}

            function focusGraphNode(nodeId) {{
                if (
                    typeof network === "undefined" ||
                    typeof nodes === "undefined"
                ) {{
                    return;
                }}

                const node = nodes.get(nodeId);

                if (!node) {{
                    return;
                }}

                const nodeType =
                    getNodeType(node.title);

                const nodeTypeCheckbox =
                    document.querySelector(
                        `.node-type-filter[data-node-type="${{nodeType}}"]`
                    );

                if (
                    nodeTypeCheckbox &&
                    !nodeTypeCheckbox.checked
                ) {{
                    nodeTypeCheckbox.checked = true;
                }}

                const nodeUpdates = [];

                nodes.forEach(function(item) {{
                    nodeUpdates.push({{
                        id: item.id,
                        hidden: false
                    }});
                }});

                nodes.update(nodeUpdates);

                updateGraphVisibility();

                network.selectNodes([nodeId]);

                network.focus(
                    nodeId,
                    {{
                        scale: 1.5,
                        animation: {{
                            duration: 600,
                            easingFunction:
                                "easeInOutQuad"
                        }}
                    }}
                );
            }}

            searchInput.addEventListener(
                "input",
                function() {{
                    renderSearchResults(
                        searchInput.value
                    );
                }}
            );
        </script>
        """

        return html.replace(
            "</body>",
            panel + "</body>",
        )