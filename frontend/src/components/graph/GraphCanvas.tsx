import { MouseEvent, PointerEvent, RefObject, WheelEvent } from "react";

import { cn } from "@/lib/utils";
import { VIEWBOX_H, VIEWBOX_W } from "@/lib/graph-layout";
import type { DragState, GraphEdge, GraphTransform, SimNode } from "@/types";
import { GraphEdges } from "./GraphEdges";
import { GraphNodes } from "./GraphNodes";

type GraphCanvasProps = {
  svgRef: RefObject<SVGSVGElement | null>;
  transform: GraphTransform;
  dragging: boolean;
  onDoubleClick: () => void;
  onPointerDown: (event: PointerEvent<SVGSVGElement>) => void;
  onPointerMove: (event: PointerEvent<SVGSVGElement>) => void;
  onPointerUp: (event: PointerEvent<SVGSVGElement>) => void;
  onPointerLeave: () => void;
  onWheel: (event: WheelEvent<SVGSVGElement>) => void;
  // GraphEdges props
  edges: GraphEdge[];
  byId: Record<string, SimNode>;
  isConnectedEdge: (edge: GraphEdge) => boolean;
  // GraphNodes props
  nodes: SimNode[];
  activeNodeId: string | null;
  dragState: DragState | null;
  filteredNodeIds: Set<string> | null;
  isConnectedNode: (nodeId: string) => boolean;
  onNodePointerDown: (event: PointerEvent<SVGGElement>, node: SimNode) => void;
  onNodeClick: (event: MouseEvent<SVGGElement>, nodeId: string) => void;
  onNodeEnter: (id: string) => void;
  onNodeLeave: () => void;
};

export function GraphCanvas({
  svgRef,
  transform,
  dragging,
  onDoubleClick,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onPointerLeave,
  onWheel,
  edges,
  byId,
  isConnectedEdge,
  nodes,
  activeNodeId,
  dragState,
  filteredNodeIds,
  isConnectedNode,
  onNodePointerDown,
  onNodeClick,
  onNodeEnter,
  onNodeLeave,
}: GraphCanvasProps) {
  return (
    <svg
      ref={svgRef}
      className={cn("graph-canvas graph-stage", dragging && "cursor-grabbing")}
      onDoubleClick={onDoubleClick}
      onPointerDown={onPointerDown}
      onPointerLeave={onPointerLeave}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onWheel={onWheel}
      role="img"
      viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
      aria-label="Interactive knowledge graph"
    >
      <defs>
        <pattern id="graph-dots" width="18" height="18" patternUnits="userSpaceOnUse">
          <circle cx="1.5" cy="1.5" r="1.2" fill="currentColor" className="text-slate-300" />
        </pattern>
      </defs>
      <rect width={VIEWBOX_W} height={VIEWBOX_H} fill="url(#graph-dots)" />
      <g transform={`translate(${transform.x} ${transform.y}) scale(${transform.scale})`}>
        <GraphEdges edges={edges} byId={byId} isConnectedEdge={isConnectedEdge} />
        <GraphNodes
          nodes={nodes}
          activeNodeId={activeNodeId}
          dragState={dragState}
          filteredNodeIds={filteredNodeIds}
          isConnectedNode={isConnectedNode}
          onNodePointerDown={onNodePointerDown}
          onNodeClick={onNodeClick}
          onNodeEnter={onNodeEnter}
          onNodeLeave={onNodeLeave}
        />
      </g>
    </svg>
  );
}
