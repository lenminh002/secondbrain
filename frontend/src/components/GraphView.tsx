import { useMemo, useState } from "react";

import { Card } from "@/components/ui/card";
import { buildAdjacency } from "@/lib/graph-layout";
import { useGraphSimulation } from "@/hooks/useGraphSimulation";
import { useGraphViewport } from "@/hooks/useGraphViewport";
import { useGraphInteractions } from "@/hooks/useGraphInteractions";
import { GraphCanvas, GraphEmptyState, GraphToolbar, NodeDetailPanel } from "@/components/graph";
import type { GraphEdge, KnowledgeGraph } from "@/types";

export function GraphView({
  graph,
  onRefresh,
}: {
  graph: KnowledgeGraph;
  onRefresh: () => void;
}) {
  const simulation = useGraphSimulation(graph);
  const viewport = useGraphViewport();
  const interactions = useGraphInteractions({ viewport, simulation });
  const [filterText, setFilterText] = useState("");

  const adjacency = useMemo(() => buildAdjacency(graph.edges), [graph.edges]);

  // Derived selectors (cross-cutting: straddles simulation output, adjacency, and interaction state)
  const activeNodeId = interactions.selectedNodeId || interactions.hoveredNodeId;
  const activeNeighbors = activeNodeId ? adjacency.neighbors.get(activeNodeId) ?? new Set<string>() : new Set<string>();
  const selectedNode = activeNodeId ? simulation.byId[activeNodeId] : null;
  const connectedNodes = [...activeNeighbors].map((id) => simulation.byId[id]).filter(Boolean);

  const filteredNodeIds = useMemo<Set<string> | null>(() => {
    const q = filterText.trim().toLowerCase();
    if (!q) return null;
    return new Set(simulation.nodes.filter((n) => n.label.toLowerCase().includes(q)).map((n) => n.id));
  }, [filterText, simulation.nodes]);

  function isConnectedNode(nodeId: string) {
    return !activeNodeId || nodeId === activeNodeId || activeNeighbors.has(nodeId);
  }

  function isConnectedEdge(edge: GraphEdge) {
    return !activeNodeId || edge.source === activeNodeId || edge.target === activeNodeId;
  }

  // resetView spans all three hooks — lives in the orchestrator
  function resetView() {
    viewport.resetTransform();
    interactions.setSelectedNodeId(null);
    simulation.reseedAndReheat();
  }

  if (!graph.nodes.length) {
    return <GraphEmptyState />;
  }

  return (
    <Card className="overflow-hidden border-slate-200 bg-white shadow-sm">
      <GraphToolbar
        onRefresh={onRefresh}
        onFit={() => viewport.fitGraph(simulation.nodes)}
        onZoomIn={() => viewport.zoomBy(1.06)}
        onZoomOut={() => viewport.zoomBy(0.94)}
        onReset={resetView}
        filterText={filterText}
        onFilterChange={setFilterText}
      />
      <div className="relative">
        <GraphCanvas
          svgRef={viewport.svgRef}
          transform={viewport.transform}
          dragging={!!interactions.dragState}
          onDoubleClick={resetView}
          onPointerDown={interactions.onBackgroundPointerDown}
          onPointerMove={interactions.onBackgroundPointerMove}
          onPointerUp={interactions.onBackgroundPointerUp}
          onPointerLeave={() => interactions.setHovered(null)}
          onWheel={viewport.onWheel}
          edges={graph.edges}
          nodes={simulation.nodes}
          byId={simulation.byId}
          activeNodeId={activeNodeId}
          dragState={interactions.dragState}
          filteredNodeIds={filteredNodeIds}
          isConnectedEdge={isConnectedEdge}
          isConnectedNode={isConnectedNode}
          onNodePointerDown={interactions.onNodePointerDown}
          onNodeClick={interactions.onNodeClick}
          onNodeEnter={interactions.setHovered}
          onNodeLeave={() => interactions.setHovered(null)}
        />
        {selectedNode && selectedNode.x != null && (
          <NodeDetailPanel
            node={selectedNode}
            neighborCount={activeNeighbors.size}
            connectedNodes={connectedNodes}
            onSelect={interactions.setSelectedNodeId}
          />
        )}
      </div>
    </Card>
  );
}
