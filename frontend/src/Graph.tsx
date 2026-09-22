import { useEffect, useRef, useState } from "react";
import cytoscape from "cytoscape";
import type { Core } from "cytoscape";
import { Focus, Plus, Minus, Network } from "lucide-react";
import type { GraphElement } from "./types";
import { sourceUrl } from "./api";

export default function Graph({
  data,
}: {
  data: { nodes: GraphElement[]; edges: GraphElement[] };
}) {
  const container = useRef<HTMLDivElement>(null);
  const graph = useRef<Core | null>(null);
  const [selected, select] = useState<GraphElement["data"] | null>(null);
  const [search, setSearch] = useState("");
  useEffect(() => {
    if (!container.current) return;
    const cy = cytoscape({
      container: container.current,
      elements: [...data.nodes, ...data.edges],
      wheelSensitivity: 0.25,
      minZoom: 0.15,
      maxZoom: 3,
      layout: {
        name: "cose",
        animate: false,
        padding: 60,
        nodeRepulsion: () => 14000,
        idealEdgeLength: () => 100,
      },
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#6092c7",
            label: "data(label)",
            color: "#b7c5d6",
            "font-size": 11,
            "text-valign": "bottom",
            "text-margin-y": 10,
            "text-wrap": "wrap",
            "text-max-width": "145px",
            width: 28,
            height: 28,
            "border-width": 5,
            "border-color": "#1b2b40",
          },
        },
        {
          selector: 'node[type="TARGET"]',
          style: {
            "background-color": "#7dd3d5",
            "border-color": "#224246",
            width: 38,
            height: 38,
            "font-weight": "bold",
          },
        },
        {
          selector: 'node[type="WEBSITE"]',
          style: {
            "background-color": "#a99ad0",
            "border-color": "#312d45",
            shape: "round-rectangle",
          },
        },
        {
          selector: 'node[type="SEARCH RESULT"]',
          style: {
            "background-color": "#b69e6d",
            "border-color": "#3d3629",
            shape: "diamond",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.2,
            "line-color": "#40556d",
            "target-arrow-color": "#40556d",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 8,
            color: "#8fa3ba",
            "text-rotation": "autorotate",
            "text-background-color": "#111820",
            "text-background-opacity": 1,
            "text-background-padding": "3px",
          },
        },
        {
          selector: ":selected",
          style: { "border-color": "#b2e9ec", "border-width": 3 },
        },
        { selector: ".dim", style: { opacity: 0.18 } },
      ],
    });
    graph.current = cy;
    cy.on("tap", "node, edge", (event) => select(event.target.data()));
    cy.on("tap", (event) => {
      if (event.target === cy) select(null);
    });
    const observer = new ResizeObserver(() => cy.resize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      cy.destroy();
      graph.current = null;
    };
  }, [data]);
  useEffect(() => {
    const cy = graph.current;
    if (!cy) return;
    cy.elements().removeClass("dim");
    if (search) {
      const matches = cy
        .nodes()
        .filter((node) =>
          String(node.data("label"))
            .toLowerCase()
            .includes(search.toLowerCase()),
        );
      cy.elements().not(matches.closedNeighborhood()).addClass("dim");
    }
  }, [search]);
  return (
    <div className="graph-shell panel">
      <div className="graph-toolbar">
        <span>
          <Network size={16} /> Evidence relationships
        </span>
        <input
          aria-label="Find graph node"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Find a node…"
        />
        <div className="button-group">
          <button
            aria-label="Zoom in"
            onClick={() =>
              graph.current?.zoom((graph.current?.zoom() || 1) * 1.2)
            }
          >
            <Plus size={16} />
          </button>
          <button
            aria-label="Zoom out"
            onClick={() =>
              graph.current?.zoom((graph.current?.zoom() || 1) / 1.2)
            }
          >
            <Minus size={16} />
          </button>
          <button
            aria-label="Fit graph"
            onClick={() => graph.current?.fit(undefined, 50)}
          >
            <Focus size={16} />
          </button>
        </div>
      </div>
      <div
        ref={container}
        className="graph-canvas"
        role="img"
        aria-label="Interactive graph of public profiles, links, and search references. Pan and pinch to explore. Equivalent source relationships are listed below."
      />
      <div className="graph-legend">
        <span>
          <i className="dot cyan" />
          Target
        </span>
        <span>
          <i className="dot blue" />
          Profile
        </span>
        <span>
          <i className="dot purple" />
          Website
        </span>
        <span>
          <i className="dot amber" />
          Search reference
        </span>
      </div>
      {selected && (
        <div className="graph-detail">
          <strong>{selected.label}</strong>
          <p>{selected.type || "Source-supported relationship"}</p>
          {sourceUrl(selected.url || selected.source_url || "") && (
            <a
              href={sourceUrl(selected.url || selected.source_url || "")}
              target="_blank"
              rel="noreferrer"
            >
              Open source ↗
            </a>
          )}
          {selected.evidence_ids && (
            <p className="mono">{selected.evidence_ids.join(" · ")}</p>
          )}
        </div>
      )}
      <details className="graph-list">
        <summary>Accessible relationship list ({data.edges.length})</summary>
        {data.edges.map((edge) => (
          <p key={edge.data.id}>
            {
              data.nodes.find((node) => node.data.id === edge.data.source)?.data
                .label
            }{" "}
            → {edge.data.label} →{" "}
            {
              data.nodes.find((node) => node.data.id === edge.data.target)?.data
                .label
            }
            <small>Evidence: {edge.data.evidence_ids?.join(", ")}</small>
          </p>
        ))}
      </details>
    </div>
  );
}
