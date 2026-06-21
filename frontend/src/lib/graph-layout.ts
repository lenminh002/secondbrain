import type { GraphEdge, GraphNode, GraphNodePositions } from "@/types";

export const VIEWBOX_W = 1040;
export const VIEWBOX_H = 680;
export const CENTER_X = 520;
export const CENTER_Y = 340;

// Golden angle in radians — distributes points without symmetric overlaps
const GOLDEN_ANGLE = 2.39996322972865;

export function computeInitialPositions(nodes: GraphNode[]): GraphNodePositions {
  const sourceNodes = nodes.filter((n) => n.type === "source");
  const tagNodes = nodes.filter((n) => n.type === "tag");
  const conceptNodes = nodes.filter((n) => n.type === "concept");

  const sourceRadius = Math.max(110, sourceNodes.length * 16);
  const tagRadius = Math.max(170, tagNodes.length * 13);
  const conceptRadius = Math.max(235, conceptNodes.length * 10);

  const positions: GraphNodePositions = {};

  sourceNodes.forEach((node, i) => {
    const angle = i * GOLDEN_ANGLE;
    positions[node.id] = { x: CENTER_X + Math.cos(angle) * sourceRadius, y: CENTER_Y + Math.sin(angle) * sourceRadius };
  });

  tagNodes.forEach((node, i) => {
    const angle = i * GOLDEN_ANGLE + Math.PI / 4;
    positions[node.id] = { x: CENTER_X + Math.cos(angle) * tagRadius, y: CENTER_Y + Math.sin(angle) * tagRadius };
  });

  conceptNodes.forEach((node, i) => {
    const ring = conceptRadius + (i % 3) * 34;
    const angle = i * GOLDEN_ANGLE + Math.PI / 6;
    positions[node.id] = { x: CENTER_X + Math.cos(angle) * ring, y: CENTER_Y + Math.sin(angle) * ring };
  });

  return positions;
}

export function buildAdjacency(edges: GraphEdge[]): {
  neighbors: Map<string, Set<string>>;
  edgeKeys: Set<string>;
} {
  const neighbors = new Map<string, Set<string>>();
  const edgeKeys = new Set<string>();
  for (const edge of edges) {
    if (!neighbors.has(edge.source)) neighbors.set(edge.source, new Set());
    if (!neighbors.has(edge.target)) neighbors.set(edge.target, new Set());
    neighbors.get(edge.source)?.add(edge.target);
    neighbors.get(edge.target)?.add(edge.source);
    edgeKeys.add(`${edge.source}->${edge.target}`);
    edgeKeys.add(`${edge.target}->${edge.source}`);
  }
  return { neighbors, edgeKeys };
}
