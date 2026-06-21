import { useEffect, useRef, useState } from "react";
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation } from "d3-force";

import { CENTER_X, CENTER_Y, computeInitialPositions } from "@/lib/graph-layout";
import type { KnowledgeGraph, SimLink, SimNode } from "@/types";

export type GraphSimulationControls = {
  /** Live in-place-mutated d3 nodes; re-renders on each physics tick. */
  nodes: SimNode[];
  /** Lookup by id recomputed each render (mirrors the byId pattern in GraphView). */
  byId: Record<string, SimNode>;
  /** Re-seed positions, clear velocity/pin, alpha(1).restart() — simulation half of resetView. */
  reseedAndReheat: () => void;
  /** Pin node at its current x/y and alphaTarget(0.3).restart(). */
  pinNode: (nodeId: string) => void;
  /** Move a pinned node to a sim-space coordinate while dragging. */
  dragNode: (nodeId: string, x: number, y: number) => void;
  /** Unpin node (fx=fy=null) and alphaTarget(0). */
  releaseNode: (nodeId: string) => void;
};

export function useGraphSimulation(graph: KnowledgeGraph): GraphSimulationControls {
  const simNodesRef = useRef<SimNode[]>([]);
  const simRef = useRef<ReturnType<typeof forceSimulation<SimNode>> | null>(null);
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    if (!graph.nodes.length) return;

    const initPos = computeInitialPositions(graph.nodes);
    const nodes: SimNode[] = graph.nodes.map((n) => ({
      ...n,
      x: initPos[n.id]?.x ?? CENTER_X,
      y: initPos[n.id]?.y ?? CENTER_Y,
    }));
    simNodesRef.current = nodes;

    const nodeById = new Map(nodes.map((n) => [n.id, n]));
    const links: SimLink[] = graph.edges
      .filter((e) => nodeById.has(e.source) && nodeById.has(e.target))
      .map((e) => ({ source: e.source, target: e.target, relation: e.relation }));

    const tickRef = { count: 0 };
    const sim = forceSimulation<SimNode>(nodes)
      .force("charge", forceManyBody<SimNode>().strength(-420))
      .force(
        "link",
        forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance(155)
          .strength(0.3),
      )
      .force("center", forceCenter(CENTER_X, CENTER_Y))
      .force(
        "collide",
        forceCollide<SimNode>((d) =>
          d.type === "source" ? 48 : d.type === "tag" ? 38 : 32,
        ),
      )
      .velocityDecay(0.35)
      .on("tick", () => {
        tickRef.count += 1;
        if (tickRef.count % 3 === 0) forceUpdate((t) => t + 1);
      });

    simRef.current = sim;
    return () => {
      sim.stop();
    };
  }, [graph.nodes, graph.edges]);

  function reseedAndReheat() {
    const sim = simRef.current;
    if (sim) {
      const initPos = computeInitialPositions(graph.nodes);
      simNodesRef.current.forEach((n) => {
        n.x = initPos[n.id]?.x ?? CENTER_X;
        n.y = initPos[n.id]?.y ?? CENTER_Y;
        n.vx = 0;
        n.vy = 0;
        n.fx = null;
        n.fy = null;
      });
      sim.alpha(1).restart();
    }
  }

  function pinNode(nodeId: string) {
    const simNode = simNodesRef.current.find((n) => n.id === nodeId);
    if (simNode) {
      simNode.fx = simNode.x;
      simNode.fy = simNode.y;
    }
    simRef.current?.alphaTarget(0.3).restart();
  }

  function dragNode(nodeId: string, x: number, y: number) {
    const simNode = simNodesRef.current.find((n) => n.id === nodeId);
    if (simNode) {
      simNode.fx = x;
      simNode.fy = y;
    }
  }

  function releaseNode(nodeId: string) {
    const simNode = simNodesRef.current.find((n) => n.id === nodeId);
    if (simNode) {
      simNode.fx = null;
      simNode.fy = null;
    }
    simRef.current?.alphaTarget(0);
  }

  const nodes = simNodesRef.current;
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));

  return { nodes, byId, reseedAndReheat, pinNode, dragNode, releaseNode };
}
