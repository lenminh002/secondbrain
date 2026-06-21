export type SourceType = "note" | "pdf" | "youtube";
export type SourceStatus = "processing" | "ready" | "failed";
export type ActiveView = "home" | "notes" | "digest" | "profile";
export type NotesMode = "note" | "graph";

export type AccountRecord = {
  id: string;
  name: string;
  handle: string;
  initials: string;
};

export type SourceRecord = {
  id: string;
  type: SourceType;
  title: string;
  source_url: string | null;
  status: SourceStatus;
  error: string | null;
  created_at: string;
};

export type SourceDetail = SourceRecord & {
  markdown: string;
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

export type DragState = {
  pointerId: number;
  startX: number;
  startY: number;
  originX: number;
  originY: number;
};

export type Citation = {
  source_id: string;
  source_title: string;
  section: string;
  text: string;
  score: number;
};

export type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
};

export type ApiError = {
  detail?: string;
};
