export type SourceType = "note" | "pdf";
export type SourceStatus = "processing" | "ready" | "failed";
export type ActiveView = "home" | "notes" | "ingest" | "chat";
export type NotesMode = "note" | "graph";

export type AccountRecord = {
  id: string;
  name: string;
  handle: string;
  initials: string;
  email?: string;
  avatar_url?: string;
};

export type SourceRecord = {
  id: string;
  type: SourceType;
  title: string;
  source_url: string | null;
  status: SourceStatus;
  error: string | null;
  created_at: string;
  progress_stage?: string;
  progress_label?: string;
  progress_percent?: number;
  // Enrichment fields (present on list items; always present on SourceDetail)
  summary?: string;
  key_ideas?: string[];
  concepts?: string[];
  claims?: string[];
  questions?: string[];
  metadata?: {
    original_file?: {
      provider?: "google_drive" | string;
      drive_file_id?: string | null;
      drive_web_view_link?: string | null;
      drive_web_content_link?: string | null;
      filename?: string | null;
      mime_type?: string | null;
      size_bytes?: number | null;
    };
  };
};

export type SourceDetail = SourceRecord & {
  content?: string;
  summary?: string;
  key_ideas?: string[];
  concepts?: string[];
  claims?: string[];
  questions?: string[];
};

export type PostRecord = {
  id: string;
  account_id: string;
  source_id: string;
  source_title: string;
  body: string;
  created_at: string;
};

export type GraphNode = {
  id: string;
  label: string;
  type: "source" | "concept";
};

export type PositionedGraphNode = GraphNode & {
  x: number;
  y: number;
};

export type GraphEdge = {
  source: string;
  target: string;
  relation: string;
};

export type KnowledgeGraph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type GraphTransform = {
  x: number;
  y: number;
  scale: number;
};

export type GraphNodePositions = Record<string, { x: number; y: number }>;

// d3-force internal simulation types (exported so hooks and subcomponents share them)
import type { SimulationLinkDatum, SimulationNodeDatum } from "d3-force";

export type SimNode = SimulationNodeDatum & {
  id: string;
  label: string;
  type: "source" | "concept";
};

export type SimLink = SimulationLinkDatum<SimNode> & {
  relation: string;
};

export type DragState = {
  mode: "pan";
  pointerId: number;
  startX: number;
  startY: number;
  originX: number;
  originY: number;
} | {
  mode: "node";
  pointerId: number;
  nodeId: string;
  startX: number;
  startY: number;
  moved: boolean;
};

export type Citation = {
  source_id: string;
  source_title: string;
  section: string;
  text: string;
  score: number;
  retrieval?: "vector" | "graph_neighbor";
  matched_concept_id?: string;
  matched_concept_label?: string;
};

export type GraphContext = {
  concept_id: string;
  concept_label: string;
  source_ids: string[];
  source_titles: string[];
  expanded_source_ids?: string[];
  expanded_source_titles?: string[];
};

export type ToolCall = {
  name: string;
};

export type AgentTraceStep = {
  stage: string;
  title: string;
  detail?: string;
  status?: string;
  metadata?: Record<string, unknown>;
};

export type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  graphContext?: GraphContext[];
  toolCalls?: ToolCall[];
  agentTrace?: AgentTraceStep[];
  isStreaming?: boolean;
};

export type ChatHistoryMessage = Pick<ChatMessage, "role" | "text">;

export type ApiError = {
  detail?: string;
};
