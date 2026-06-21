import { MouseEvent, PointerEvent } from "react";

import { cn } from "@/lib/utils";
import type { DragState, SimNode } from "@/types";

type GraphNodesProps = {
  nodes: SimNode[];
  activeNodeId: string | null;
  dragState: DragState | null;
  isConnectedNode: (nodeId: string) => boolean;
  filteredNodeIds: Set<string> | null;
  onNodePointerDown: (event: PointerEvent<SVGGElement>, node: SimNode) => void;
  onNodeClick: (event: MouseEvent<SVGGElement>, nodeId: string) => void;
  onNodeEnter: (id: string) => void;
  onNodeLeave: () => void;
};

export function GraphNodes({
  nodes,
  activeNodeId,
  dragState,
  isConnectedNode,
  filteredNodeIds,
  onNodePointerDown,
  onNodeClick,
  onNodeEnter,
  onNodeLeave,
}: GraphNodesProps) {
  return (
    <>
      {nodes.map((node) => {
        if (node.x == null || node.y == null) return null;
        const active = isConnectedNode(node.id);
        const selected = activeNodeId === node.id;
        const dragging = dragState?.mode === "node" && dragState.nodeId === node.id;
        const searchDimmed = filteredNodeIds !== null && !filteredNodeIds.has(node.id);
        const radius = node.type === "source" ? 24 : node.type === "tag" ? 18 : 15;
        return (
          <g
            className={cn("graph-node", node.type, active ? "is-active" : "is-dimmed", selected && "is-selected", dragging && "is-dragging")}
            data-graph-node="true"
            key={node.id}
            onClick={(event) => onNodeClick(event, node.id)}
            onPointerDown={(event) => onNodePointerDown(event, node)}
            onPointerEnter={() => onNodeEnter(node.id)}
            onPointerLeave={onNodeLeave}
            style={searchDimmed ? { opacity: 0.1 } : undefined}
            transform={`translate(${node.x}, ${node.y})`}
          >
            <circle r={radius} />
            <text y={radius + 20}>{node.label.slice(0, 26)}</text>
          </g>
        );
      })}
    </>
  );
}
