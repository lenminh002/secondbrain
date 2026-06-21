import { Badge } from "@/components/ui/badge";
import { isQualityConcept } from "@/lib/concepts";
import type { SimNode } from "@/types";

type NodeDetailPanelProps = {
  node: SimNode;
  neighborCount: number;
  connectedNodes: SimNode[];
  onSelect: (nodeId: string) => void;
};

export function NodeDetailPanel({ node, neighborCount, connectedNodes, onSelect }: NodeDetailPanelProps) {
  const visibleConnectedNodes = connectedNodes.filter((connectedNode) => (
    connectedNode.type !== "concept" || isQualityConcept(connectedNode.label)
  ));

  return (
    <div className="absolute right-4 top-4 w-72 rounded-xl border bg-white/95 p-4 shadow-xl backdrop-blur">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{node.type}</div>
          <div className="mt-1 font-bold">{node.label}</div>
        </div>
        <Badge variant={node.type === "source" ? "default" : "secondary"}>{neighborCount} links</Badge>
      </div>
      <div className="mt-4 space-y-2">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Connected nodes</div>
        {visibleConnectedNodes.length ? (
          <div className="max-h-44 space-y-1 overflow-auto pr-1">
            {visibleConnectedNodes.map((n) => (
              <button
                className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-sm hover:bg-muted"
                key={n.id}
                onClick={() => onSelect(n.id)}
                type="button"
              >
                <span className="truncate">{n.label}</span>
                <span className="text-xs capitalize text-muted-foreground">{n.type}</span>
              </button>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">No direct connections.</div>
        )}
      </div>
    </div>
  );
}
