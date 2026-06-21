import { cn } from "@/lib/utils";
import type { GraphEdge, SimNode } from "@/types";

type GraphEdgesProps = {
  edges: GraphEdge[];
  byId: Record<string, SimNode>;
  isConnectedEdge: (edge: GraphEdge) => boolean;
};

export function GraphEdges({ edges, byId, isConnectedEdge }: GraphEdgesProps) {
  return (
    <>
      {edges.map((edge) => {
        const source = byId[edge.source];
        const target = byId[edge.target];
        if (!source || !target || source.x == null || target.x == null) return null;
        const active = isConnectedEdge(edge);
        const midX = ((source.x ?? 0) + (target.x ?? 0)) / 2;
        const midY = ((source.y ?? 0) + (target.y ?? 0)) / 2;
        const isTagged = edge.relation === "tagged_as";
        return (
          <g
            className={cn("graph-edge", isTagged && "tagged-as", active ? "is-active" : "is-dimmed")}
            key={`${edge.source}-${edge.target}-${edge.relation}`}
          >
            <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} />
            {active && (
              <text className="graph-edge-label" x={midX} y={midY - 6}>
                {edge.relation}
              </text>
            )}
          </g>
        );
      })}
    </>
  );
}
