import { MouseEvent, PointerEvent, WheelEvent, useEffect, useMemo, useRef, useState } from "react";
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation } from "d3-force";
import type { SimulationLinkDatum, SimulationNodeDatum } from "d3-force";
import { GitBranch, RefreshCcw, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { DragState, GraphEdge, GraphTransform, KnowledgeGraph } from "@/types";

// Internal simulation node — d3-force mutates x, y, vx, vy, fx, fy in place
type SimNode = SimulationNodeDatum & {
  id: string;
  label: string;
  type: "source" | "concept";
};

type SimLink = SimulationLinkDatum<SimNode> & {
  relation: string;
};

// Seed initial positions the same way the old trig layout did so the
// first tick starts from a well-spread state rather than the origin.
function computeInitialPositions(nodes: KnowledgeGraph["nodes"]): Record<string, { x: number; y: number }> {
  const sourceNodes = nodes.filter((n) => n.type === "source");
  const conceptNodes = nodes.filter((n) => n.type === "concept");
  const cx = 520;
  const cy = 340;
  const sourceRadius = Math.max(88, sourceNodes.length * 16);
  const conceptRadius = Math.max(210, conceptNodes.length * 11);
  const positions: Record<string, { x: number; y: number }> = {};
  sourceNodes.forEach((node, i) => {
    const angle = (i / Math.max(sourceNodes.length, 1)) * Math.PI * 2 - Math.PI / 2;
    positions[node.id] = { x: cx + Math.cos(angle) * sourceRadius, y: cy + Math.sin(angle) * sourceRadius };
  });
  conceptNodes.forEach((node, i) => {
    const ring = conceptRadius + (i % 3) * 46;
    const angle = (i / Math.max(conceptNodes.length, 1)) * Math.PI * 2 + Math.PI / 8;
    positions[node.id] = { x: cx + Math.cos(angle) * ring, y: cy + Math.sin(angle) * ring };
  });
  return positions;
}

export function GraphView({
  graph,
  onRefresh,
}: {
  graph: KnowledgeGraph;
  onRefresh: () => void;
}) {
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [transform, setTransform] = useState<GraphTransform>({ x: 0, y: 0, scale: 1 });
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [suppressClickNodeId, setSuppressClickNodeId] = useState<string | null>(null);

  // Sim nodes are mutated in-place by d3; we keep a ref and bump a counter
  // to trigger React re-renders on each physics tick.
  const simNodesRef = useRef<SimNode[]>([]);
  const simRef = useRef<ReturnType<typeof forceSimulation<SimNode>> | null>(null);
  const [, forceUpdate] = useState(0);

  const svgRef = useRef<SVGSVGElement>(null);

  // Stable adjacency map used for highlight / popup
  const adjacency = useMemo(() => {
    const neighbors = new Map<string, Set<string>>();
    const edgeKeys = new Set<string>();
    for (const edge of graph.edges) {
      if (!neighbors.has(edge.source)) neighbors.set(edge.source, new Set());
      if (!neighbors.has(edge.target)) neighbors.set(edge.target, new Set());
      neighbors.get(edge.source)?.add(edge.target);
      neighbors.get(edge.target)?.add(edge.source);
      edgeKeys.add(`${edge.source}->${edge.target}`);
      edgeKeys.add(`${edge.target}->${edge.source}`);
    }
    return { neighbors, edgeKeys };
  }, [graph.edges]);

  // Build / rebuild the simulation whenever graph data changes
  useEffect(() => {
    if (!graph.nodes.length) return;

    const initPos = computeInitialPositions(graph.nodes);
    const nodes: SimNode[] = graph.nodes.map((n) => ({
      ...n,
      x: initPos[n.id]?.x ?? 520,
      y: initPos[n.id]?.y ?? 340,
    }));
    simNodesRef.current = nodes;

    const nodeById = new Map(nodes.map((n) => [n.id, n]));
    const links: SimLink[] = graph.edges
      .filter((e) => nodeById.has(e.source) && nodeById.has(e.target))
      .map((e) => ({ source: e.source, target: e.target, relation: e.relation }));

    const sim = forceSimulation<SimNode>(nodes)
      .force("charge", forceManyBody<SimNode>().strength(-220))
      .force(
        "link",
        forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance(90)
          .strength(0.6),
      )
      .force("center", forceCenter(520, 340))
      .force("collide", forceCollide<SimNode>((d) => (d.type === "source" ? 30 : 20)))
      .velocityDecay(0.4)
      .on("tick", () => {
        // d3 mutates nodes in-place; bump counter to re-render
        forceUpdate((t) => t + 1);
      });

    simRef.current = sim;
    return () => {
      sim.stop();
    };
  }, [graph.nodes, graph.edges]);

  // Convert a client pointer position to simulation coordinate space,
  // accounting for the SVG viewBox scaling and the <g> pan/zoom transform.
  function clientToSim(clientX: number, clientY: number): { x: number; y: number } {
    const svg = svgRef.current;
    if (!svg) return { x: clientX, y: clientY };
    const rect = svg.getBoundingClientRect();
    const vbX = (clientX - rect.left) * (1040 / rect.width);
    const vbY = (clientY - rect.top) * (680 / rect.height);
    return {
      x: (vbX - transform.x) / transform.scale,
      y: (vbY - transform.y) / transform.scale,
    };
  }

  // Read live node positions from the sim ref for this render frame
  const renderedNodes = simNodesRef.current;
  const byId = Object.fromEntries(renderedNodes.map((n) => [n.id, n]));

  const activeNodeId = selectedNodeId || hoveredNodeId;
  const activeNeighbors = activeNodeId ? adjacency.neighbors.get(activeNodeId) ?? new Set<string>() : new Set<string>();
  const selectedNode = activeNodeId ? byId[activeNodeId] : null;
  const connectedNodes = [...activeNeighbors].map((id) => byId[id]).filter(Boolean);

  function isConnectedNode(nodeId: string) {
    return !activeNodeId || nodeId === activeNodeId || activeNeighbors.has(nodeId);
  }

  function isConnectedEdge(edge: GraphEdge) {
    return !activeNodeId || edge.source === activeNodeId || edge.target === activeNodeId;
  }

  function resetView() {
    setTransform({ x: 0, y: 0, scale: 1 });
    setSelectedNodeId(null);
    // Re-seed positions and reheat the simulation
    const sim = simRef.current;
    if (sim) {
      const initPos = computeInitialPositions(graph.nodes);
      simNodesRef.current.forEach((n) => {
        n.x = initPos[n.id]?.x ?? 520;
        n.y = initPos[n.id]?.y ?? 340;
        n.vx = 0;
        n.vy = 0;
        n.fx = null;
        n.fy = null;
      });
      sim.alpha(1).restart();
    }
  }

  function fitGraph() {
    if (!renderedNodes.length) return;
    const xs = renderedNodes.map((n) => n.x ?? 0);
    const ys = renderedNodes.map((n) => n.y ?? 0);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const graphWidth = Math.max(maxX - minX, 1);
    const graphHeight = Math.max(maxY - minY, 1);
    const scale = Math.min(1.25, Math.max(0.55, Math.min(900 / graphWidth, 560 / graphHeight) * 0.75));
    setTransform({
      scale,
      x: 520 - ((minX + maxX) / 2) * scale,
      y: 340 - ((minY + maxY) / 2) * scale,
    });
  }

  function zoomBy(factor: number) {
    setTransform((current) => ({
      ...current,
      scale: Math.min(2.4, Math.max(0.35, current.scale * factor)),
    }));
  }

  function onWheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    // Zoom by 2% per wheel tick for a slower, smoother interaction
    zoomBy(event.deltaY > 0 ? 0.98 : 1.02);
  }

  function onPointerDown(event: PointerEvent<SVGSVGElement>) {
    if (event.target instanceof SVGElement && event.target.closest("[data-graph-node='true']")) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragState({
      mode: "pan",
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: transform.x,
      originY: transform.y,
    });
  }

  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!dragState || dragState.pointerId !== event.pointerId) return;

    if (dragState.mode === "pan") {
      setTransform((current) => ({
        ...current,
        x: dragState.originX + event.clientX - dragState.startX,
        y: dragState.originY + event.clientY - dragState.startY,
      }));
      return;
    }

    // Node drag — move the pinned node to follow the pointer in sim space;
    // d3-force pulls the rest of the graph along automatically.
    const simPos = clientToSim(event.clientX, event.clientY);
    const simNode = simNodesRef.current.find((n) => n.id === dragState.nodeId);
    if (simNode) {
      simNode.fx = simPos.x;
      simNode.fy = simPos.y;
    }
    const moved = dragState.moved || Math.hypot(event.clientX - dragState.startX, event.clientY - dragState.startY) > 4;
    if (moved !== dragState.moved) {
      setDragState({ ...dragState, moved });
    }
  }

  function onPointerUp(event: PointerEvent<SVGSVGElement>) {
    if (dragState?.pointerId !== event.pointerId) return;
    if (dragState.mode === "pan") {
      // A background tap that didn't move = deselect
      const moved = Math.hypot(event.clientX - dragState.startX, event.clientY - dragState.startY) > 4;
      if (!moved) setSelectedNodeId(null);
    } else if (dragState.mode === "node") {
      if (dragState.moved) {
        setSuppressClickNodeId(dragState.nodeId);
        setSelectedNodeId(dragState.nodeId);
      }
      // Unpin the node and let the sim cool back down
      const simNode = simNodesRef.current.find((n) => n.id === dragState.nodeId);
      if (simNode) {
        simNode.fx = null;
        simNode.fy = null;
      }
      simRef.current?.alphaTarget(0);
    }
    setDragState(null);
  }

  function onNodePointerDown(event: PointerEvent<SVGGElement>, node: SimNode) {
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    // Pin the node to its current position and reheat the sim so neighbors respond
    const simNode = simNodesRef.current.find((n) => n.id === node.id);
    if (simNode) {
      simNode.fx = simNode.x;
      simNode.fy = simNode.y;
    }
    simRef.current?.alphaTarget(0.3).restart();
    setDragState({
      mode: "node",
      pointerId: event.pointerId,
      nodeId: node.id,
      startX: event.clientX,
      startY: event.clientY,
      moved: false,
    });
  }

  function onNodeClick(event: MouseEvent<SVGGElement>, nodeId: string) {
    event.stopPropagation();
    if (suppressClickNodeId === nodeId) {
      setSuppressClickNodeId(null);
      return;
    }
    setSelectedNodeId((current) => (current === nodeId ? null : nodeId));
  }

  if (!graph.nodes.length) {
    return (
      <Card className="grid min-h-[420px] place-items-center border-dashed">
        <CardContent className="pt-6 text-center">
          <GitBranch className="mx-auto mb-4 h-10 w-10 text-muted-foreground" />
          <p className="font-semibold">No graph nodes yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Digest a source, then graphify the knowledge base.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b bg-slate-50/70 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full bg-slate-950" />
            Source
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full bg-sky-500" />
            Concept
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
            Selected
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={onRefresh} size="sm" variant="outline">
            <RefreshCcw className="h-3.5 w-3.5" />
            Refresh
          </Button>
          <Button onClick={fitGraph} size="sm" variant="outline">Fit Graph</Button>
          <Button onClick={() => zoomBy(1.06)} size="icon" variant="outline">
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button onClick={() => zoomBy(0.94)} size="icon" variant="outline">
            <ZoomOut className="h-4 w-4" />
          </Button>
          <Button onClick={resetView} size="icon" variant="outline">
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="relative">
        <svg
          ref={svgRef}
          className={cn("graph-canvas graph-stage", dragState && "cursor-grabbing")}
          onDoubleClick={resetView}
          onPointerDown={onPointerDown}
          onPointerLeave={() => setHoveredNodeId(null)}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onWheel={onWheel}
          role="img"
          viewBox="0 0 1040 680"
          aria-label="Interactive knowledge graph"
        >
          <defs>
            <pattern id="graph-dots" width="18" height="18" patternUnits="userSpaceOnUse">
              <circle cx="1.5" cy="1.5" r="1.2" fill="currentColor" className="text-slate-300" />
            </pattern>
          </defs>
          <rect width="1040" height="680" fill="url(#graph-dots)" />
          <g transform={`translate(${transform.x} ${transform.y}) scale(${transform.scale})`}>
            {graph.edges.map((edge) => {
              const source = byId[edge.source];
              const target = byId[edge.target];
              if (!source || !target || source.x == null || target.x == null) return null;
              const active = isConnectedEdge(edge);
              const midX = ((source.x ?? 0) + (target.x ?? 0)) / 2;
              const midY = ((source.y ?? 0) + (target.y ?? 0)) / 2;
              return (
                <g className={cn("graph-edge", active ? "is-active" : "is-dimmed")} key={`${edge.source}-${edge.target}-${edge.relation}`}>
                  <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} />
                  {active && (
                    <text className="graph-edge-label" x={midX} y={midY - 6}>
                      {edge.relation}
                    </text>
                  )}
                </g>
              );
            })}
            {renderedNodes.map((node) => {
              if (node.x == null || node.y == null) return null;
              const active = isConnectedNode(node.id);
              const selected = activeNodeId === node.id;
              const dragging = dragState?.mode === "node" && dragState.nodeId === node.id;
              const radius = node.type === "source" ? 24 : 15;
              return (
                <g
                  className={cn("graph-node", node.type, active ? "is-active" : "is-dimmed", selected && "is-selected", dragging && "is-dragging")}
                  data-graph-node="true"
                  key={node.id}
                  onClick={(event) => onNodeClick(event, node.id)}
                  onPointerDown={(event) => onNodePointerDown(event, node)}
                  onPointerEnter={() => setHoveredNodeId(node.id)}
                  onPointerLeave={() => setHoveredNodeId(null)}
                  transform={`translate(${node.x}, ${node.y})`}
                >
                  <circle r={radius} />
                  <text y={radius + 20}>{node.label.slice(0, 26)}</text>
                </g>
              );
            })}
          </g>
        </svg>
        {selectedNode && selectedNode.x != null && (
          <div className="absolute right-4 top-4 w-72 rounded-xl border bg-white/95 p-4 shadow-xl backdrop-blur">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{selectedNode.type}</div>
                <div className="mt-1 font-bold">{selectedNode.label}</div>
              </div>
              <Badge variant={selectedNode.type === "source" ? "default" : "secondary"}>{activeNeighbors.size} links</Badge>
            </div>
            <div className="mt-4 space-y-2">
              <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Connected nodes</div>
              {connectedNodes.length ? (
                <div className="max-h-44 space-y-1 overflow-auto pr-1">
                  {connectedNodes.map((node) => (
                    <button
                      className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-sm hover:bg-muted"
                      key={node.id}
                      onClick={() => setSelectedNodeId(node.id)}
                      type="button"
                    >
                      <span className="truncate">{node.label}</span>
                      <span className="text-xs capitalize text-muted-foreground">{node.type}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">No direct connections.</div>
              )}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
