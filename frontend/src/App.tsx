import {
  Bell,
  BookOpen,
  Bot,
  CheckCircle2,
  CircleUserRound,
  Compass,
  FileText,
  GitBranch,
  Home,
  Loader2,
  MessageCircle,
  PenLine,
  RefreshCcw,
  RotateCcw,
  Search,
  Settings,
  Sparkles,
  Upload,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { FormEvent, PointerEvent, WheelEvent, useEffect, useMemo, useState } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

type SourceType = "note" | "pdf" | "youtube";
type SourceStatus = "processing" | "ready" | "failed";
type ActiveView = "home" | "notes" | "digest";
type NotesMode = "note" | "graph";

type SourceRecord = {
  id: string;
  type: SourceType;
  title: string;
  source_url: string | null;
  status: SourceStatus;
  error: string | null;
  created_at: string;
};

type SourceDetail = SourceRecord & {
  markdown: string;
};

type PostRecord = {
  id: string;
  source_id: string;
  source_title: string;
  body: string;
  created_at: string;
};

type GraphNode = {
  id: string;
  label: string;
  type: "source" | "concept";
};

type PositionedGraphNode = GraphNode & {
  x: number;
  y: number;
};

type GraphEdge = {
  source: string;
  target: string;
  relation: string;
};

type KnowledgeGraph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

type GraphTransform = {
  x: number;
  y: number;
  scale: number;
};

type DragState = {
  pointerId: number;
  startX: number;
  startY: number;
  originX: number;
  originY: number;
};

type Citation = {
  source_id: string;
  source_title: string;
  section: string;
  text: string;
  score: number;
};

type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
};

type ApiError = {
  detail?: string;
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function formatDate(value: string) {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(value));
}

function StatusBadge({ status }: { status: SourceStatus }) {
  const variant = status === "failed" ? "destructive" : status === "ready" ? "default" : "secondary";
  return (
    <Badge className={cn("capitalize", status === "processing" && "text-muted-foreground")} variant={variant}>
      {status === "processing" && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
      {status}
    </Badge>
  );
}

function MarkdownView({ markdown }: { markdown: string }) {
  if (!markdown) {
    return <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">No note selected.</div>;
  }

  return (
    <div className="markdown-body">
      {markdown
        .split("\n")
        .filter((line) => !line.startsWith("---") && !line.startsWith("id:") && !line.startsWith("type:") && !line.startsWith("title:") && !line.startsWith("source_url:") && !line.startsWith("created_at:"))
        .map((line, index) => {
          if (line.startsWith("# ")) return <h1 key={index}>{line.replace("# ", "")}</h1>;
          if (line.startsWith("## ")) return <h2 key={index}>{line.replace("## ", "")}</h2>;
          if (line.startsWith("- ")) return <li key={index}>{line.replace("- ", "")}</li>;
          if (!line.trim()) return <div key={index} className="h-2" />;
          return <p key={index}>{line}</p>;
        })}
    </div>
  );
}

function GraphView({
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

  const positioned = useMemo<PositionedGraphNode[]>(() => {
    const nodes = graph.nodes || [];
    const sourceNodes = nodes.filter((node) => node.type === "source");
    const conceptNodes = nodes.filter((node) => node.type === "concept");
    const centerX = 520;
    const centerY = 340;
    const sourceRadius = Math.max(88, sourceNodes.length * 16);
    const conceptRadius = Math.max(210, conceptNodes.length * 11);

    const sourcePositions = sourceNodes.map((node, index) => {
      const angle = (index / Math.max(sourceNodes.length, 1)) * Math.PI * 2 - Math.PI / 2;
      return {
        ...node,
        x: centerX + Math.cos(angle) * sourceRadius,
        y: centerY + Math.sin(angle) * sourceRadius,
      };
    });

    const conceptPositions = conceptNodes.map((node, index) => {
      const degree = adjacency.neighbors.get(node.id)?.size || 1;
      const ring = conceptRadius + (index % 3) * 46 + Math.min(degree, 4) * 8;
      const angle = (index / Math.max(conceptNodes.length, 1)) * Math.PI * 2 + Math.PI / 8;
      return {
        ...node,
        x: centerX + Math.cos(angle) * ring,
        y: centerY + Math.sin(angle) * ring,
      };
    });

    return [...sourcePositions, ...conceptPositions];
  }, [adjacency.neighbors, graph.nodes]);
  const byId = Object.fromEntries(positioned.map((node) => [node.id, node]));
  const activeNodeId = selectedNodeId || hoveredNodeId;
  const activeNeighbors = activeNodeId ? adjacency.neighbors.get(activeNodeId) || new Set<string>() : new Set<string>();
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
  }

  function fitGraph() {
    if (!positioned.length) return;
    const minX = Math.min(...positioned.map((node) => node.x));
    const maxX = Math.max(...positioned.map((node) => node.x));
    const minY = Math.min(...positioned.map((node) => node.y));
    const maxY = Math.max(...positioned.map((node) => node.y));
    const graphWidth = Math.max(maxX - minX, 1);
    const graphHeight = Math.max(maxY - minY, 1);
    const scale = Math.min(1.25, Math.max(0.55, Math.min(900 / graphWidth, 560 / graphHeight) * 0.75));
    setTransform({
      scale,
      x: 520 - ((minX + maxX) / 2) * scale,
      y: 340 - ((minY + maxY) / 2) * scale,
    });
  }

  function zoomBy(delta: number) {
    setTransform((current) => ({
      ...current,
      scale: Math.min(2.4, Math.max(0.35, current.scale + delta)),
    }));
  }

  function onWheel(event: WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    const direction = event.deltaY > 0 ? -0.08 : 0.08;
    zoomBy(direction);
  }

  function onPointerDown(event: PointerEvent<SVGSVGElement>) {
    if (event.target instanceof SVGElement && event.target.closest("[data-graph-node='true']")) {
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragState({
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: transform.x,
      originY: transform.y,
    });
  }

  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!dragState || dragState.pointerId !== event.pointerId) return;
    setTransform((current) => ({
      ...current,
      x: dragState.originX + event.clientX - dragState.startX,
      y: dragState.originY + event.clientY - dragState.startY,
    }));
  }

  function onPointerUp(event: PointerEvent<SVGSVGElement>) {
    if (dragState?.pointerId === event.pointerId) {
      setDragState(null);
    }
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
          <Button onClick={() => zoomBy(0.12)} size="icon" variant="outline">
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button onClick={() => zoomBy(-0.12)} size="icon" variant="outline">
            <ZoomOut className="h-4 w-4" />
          </Button>
          <Button onClick={resetView} size="icon" variant="outline">
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="relative">
        <svg
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
              if (!source || !target) return null;
              const active = isConnectedEdge(edge);
              const midX = (source.x + target.x) / 2;
              const midY = (source.y + target.y) / 2;
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
            {positioned.map((node) => {
              const active = isConnectedNode(node.id);
              const selected = activeNodeId === node.id;
              const radius = node.type === "source" ? 24 : 15;
              return (
                <g
                  className={cn("graph-node", node.type, active ? "is-active" : "is-dimmed", selected && "is-selected")}
                  data-graph-node="true"
                  key={node.id}
                  onClick={(event) => {
                    event.stopPropagation();
                    setSelectedNodeId((current) => (current === node.id ? null : node.id));
                  }}
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
        {selectedNode && (
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

function Logo() {
  return (
    <div className="flex items-center gap-3">
      <div className="grid h-9 w-9 place-items-center rounded-lg bg-primary text-primary-foreground">
        <PenLine className="h-5 w-5" />
      </div>
      <div>
        <div className="text-xl font-black tracking-tight">Second Signal</div>
        <div className="text-xs text-muted-foreground">@personal-kb</div>
      </div>
    </div>
  );
}

function TopBar() {
  return (
    <header className="sticky top-0 z-30 flex h-[74px] items-center justify-between border-b bg-background/95 px-5 backdrop-blur">
      <Logo />
      <div className="hidden w-full max-w-md items-center gap-2 rounded-full border bg-muted/35 px-3 py-2 md:flex">
        <Search className="h-4 w-4 text-muted-foreground" />
        <input className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground" placeholder="Search notes, concepts, posts..." />
      </div>
      <div className="flex items-center gap-3">
        <Button className="hidden md:inline-flex" size="icon" variant="ghost">
          <Search className="h-5 w-5" />
        </Button>
        <Avatar>
          <AvatarFallback>SS</AvatarFallback>
        </Avatar>
      </div>
    </header>
  );
}

type NavProps = {
  activeView: ActiveView;
  notesMode: NotesMode;
  setActiveView: (view: ActiveView) => void;
  setNotesMode: (mode: NotesMode) => void;
};

function SidebarNav({ activeView, notesMode, setActiveView, setNotesMode }: NavProps) {
  const items = [
    { label: "Home", icon: Home, active: activeView === "home", action: () => setActiveView("home") },
    { label: "Notes", icon: BookOpen, active: activeView === "notes" && notesMode === "note", action: () => { setActiveView("notes"); setNotesMode("note"); } },
    { label: "Graph", icon: GitBranch, active: activeView === "notes" && notesMode === "graph", action: () => { setActiveView("notes"); setNotesMode("graph"); } },
  ];

  return (
    <aside className="sticky top-[74px] hidden h-[calc(100vh-74px)] border-r bg-background px-5 py-7 lg:block">
      <div className="mb-8 flex items-center gap-3">
        <Avatar className="h-14 w-14">
          <AvatarFallback>SS</AvatarFallback>
        </Avatar>
        <div className="text-sm text-muted-foreground">@you</div>
      </div>
      <nav className="space-y-1">
        {items.map((item) => (
          <Button
            className={cn("w-full justify-start gap-3 text-base", item.active ? "text-foreground" : "text-muted-foreground")}
            key={item.label}
            onClick={item.action}
            variant={item.active ? "secondary" : "ghost"}
          >
            <item.icon className="h-5 w-5" />
            {item.label}
          </Button>
        ))}
        {[
          { label: "Explore", icon: Compass },
          { label: "Notifications", icon: Bell },
          { label: "Profile", icon: CircleUserRound },
          { label: "Settings", icon: Settings },
        ].map((item) => (
          <Button className="w-full justify-start gap-3 text-base text-muted-foreground" disabled key={item.label} variant="ghost">
            <item.icon className="h-5 w-5" />
            {item.label}
          </Button>
        ))}
      </nav>
      <Button className="mt-6 w-full gap-2" onClick={() => setActiveView("digest")}>
        <Upload className="h-4 w-4" />
        Digest Source
      </Button>
    </aside>
  );
}

function MobileNav({ activeView, setActiveView }: Pick<NavProps, "activeView" | "setActiveView">) {
  return (
    <nav className="mobile-bottom-nav fixed inset-x-0 bottom-0 z-40 grid grid-cols-3 gap-2 border-t bg-background p-3 lg:hidden">
      <Button className="h-12 text-base" onClick={() => setActiveView("home")} variant={activeView === "home" ? "default" : "outline"}>
        <Home className="h-5 w-5" />
        Home
      </Button>
      <Button className="h-12 text-base" onClick={() => setActiveView("notes")} variant={activeView === "notes" ? "default" : "outline"}>
        <BookOpen className="h-5 w-5" />
        Notes
      </Button>
      <Button className="h-12 text-base" onClick={() => setActiveView("digest")} variant={activeView === "digest" ? "default" : "outline"}>
        <Upload className="h-5 w-5" />
        Digest
      </Button>
    </nav>
  );
}

function DigestSourcePage({
  activeType,
  isSubmitting,
  noteText,
  notice,
  pdfFile,
  setActiveType,
  setNoteText,
  setPdfFile,
  setTitle,
  setYoutubeUrl,
  submitSource,
  title,
  youtubeUrl,
}: {
  activeType: SourceType;
  isSubmitting: boolean;
  noteText: string;
  notice: string;
  pdfFile: File | null;
  setActiveType: (type: SourceType) => void;
  setNoteText: (value: string) => void;
  setPdfFile: (file: File | null) => void;
  setTitle: (value: string) => void;
  setYoutubeUrl: (value: string) => void;
  submitSource: (event: FormEvent<HTMLFormElement>) => void;
  title: string;
  youtubeUrl: string;
}) {
  return (
    <main className="min-h-[calc(100vh-74px)] border-r">
      <div className="flex h-14 items-center justify-between border-b px-6">
        <div>
          <h1 className="font-bold">Digest Source</h1>
          <p className="text-xs text-muted-foreground">Turn notes, papers, and videos into structured memory.</p>
        </div>
        <Badge variant="secondary">
          <Sparkles className="mr-1 h-3 w-3" />
          AI pipeline
        </Badge>
      </div>
      <ScrollArea className="h-[calc(100vh-128px)]">
        <div className="mx-auto grid max-w-5xl gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="overflow-hidden">
            <CardHeader className="border-b bg-muted/25">
              <CardTitle className="flex items-center gap-2 text-2xl">
                <Upload className="h-5 w-5" />
                Add to your knowledge base
              </CardTitle>
              <CardDescription>
                The digest pipeline creates canonical markdown, generated posts, chunks, embeddings, and graph nodes.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-5">
              <form className="space-y-5" onSubmit={submitSource}>
                  <Tabs value={activeType} onValueChange={(value) => setActiveType(value as SourceType)}>
                    <TabsList className="grid w-full grid-cols-3">
                      <TabsTrigger value="note">Note</TabsTrigger>
                      <TabsTrigger value="pdf">PDF</TabsTrigger>
                      <TabsTrigger disabled value="youtube">Video</TabsTrigger>
                    </TabsList>
                  </Tabs>
                  <p className="text-xs text-muted-foreground">Video ingestion to be fixed.</p>

                <div className="space-y-2">
                  <label className="text-sm font-semibold" htmlFor="digest-title">Title</label>
                  <Input id="digest-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Research paper, lecture, book chapter..." />
                </div>

                {activeType === "note" && (
                  <div className="space-y-2">
                    <label className="text-sm font-semibold" htmlFor="digest-note">Notes</label>
                    <Textarea
                      id="digest-note"
                      value={noteText}
                      onChange={(event) => setNoteText(event.target.value)}
                      placeholder="Paste highlights, rough notes, or ideas you consumed."
                      rows={14}
                    />
                  </div>
                )}

                {activeType === "pdf" && (
                  <div className="space-y-2">
                    <label className="text-sm font-semibold" htmlFor="digest-pdf">PDF</label>
                    <Input id="digest-pdf" accept="application/pdf" type="file" onChange={(event) => setPdfFile(event.target.files?.[0] || null)} />
                    <p className="text-xs text-muted-foreground">{pdfFile ? `${pdfFile.name} selected` : "Upload a readable PDF with selectable text."}</p>
                  </div>
                )}

                {activeType === "youtube" && (
                  <div className="space-y-2">
                    <label className="text-sm font-semibold" htmlFor="digest-youtube">YouTube URL</label>
                    <Input id="digest-youtube" value={youtubeUrl} onChange={(event) => setYoutubeUrl(event.target.value)} placeholder="https://youtube.com/watch?v=..." />
                    <p className="text-xs text-muted-foreground">MVP uses available captions/transcripts only.</p>
                  </div>
                )}

                {notice && <div className="rounded-lg border border-destructive/25 bg-destructive/5 p-3 text-sm text-destructive">{notice}</div>}

                <Button className="h-11 w-full" disabled={isSubmitting} type="submit">
                  {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                  Digest source
                </Button>
              </form>
            </CardContent>
          </Card>

          <div className="space-y-5">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <CheckCircle2 className="h-4 w-4" />
                  What happens next
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                <p>1. Extract readable content from the source.</p>
                <p>2. Normalize it into canonical markdown.</p>
                <p>3. Generate summary, concepts, claims, and a social post.</p>
                <p>4. Add chunks to retrieval and concepts to the graph.</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Output surfaces</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                <Badge variant="secondary">Notes vault</Badge>
                <Badge variant="secondary">Home feed</Badge>
                <Badge variant="secondary">Graph</Badge>
                <Badge variant="secondary">Chat context</Badge>
              </CardContent>
            </Card>
          </div>
        </div>
      </ScrollArea>
    </main>
  );
}

function ChatPanel({
  chatInput,
  chatLog,
  isChatting,
  setChatInput,
  submitChat,
}: {
  chatInput: string;
  chatLog: ChatMessage[];
  isChatting: boolean;
  setChatInput: (value: string) => void;
  submitChat: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <Card className="flex h-full min-h-0 flex-col rounded-none border-0 border-l shadow-none lg:rounded-none">
      <CardHeader className="border-b">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          <CardTitle>AI Sidebar</CardTitle>
        </div>
        <CardDescription>Ask across notes, graph nodes, and generated posts.</CardDescription>
      </CardHeader>
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-3 p-4">
          {chatLog.length ? (
            chatLog.map((message, index) => (
              <div
                className={cn(
                  "rounded-2xl border p-3 text-sm leading-6",
                  message.role === "user" ? "ml-8 bg-primary text-primary-foreground" : "mr-8 bg-muted/45",
                )}
                key={`${message.role}-${index}`}
              >
                <p>{message.text}</p>
                {!!message.citations?.length && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {message.citations.map((citation) => (
                      <Badge key={`${citation.source_id}-${citation.section}`} variant="secondary">
                        {citation.source_title} / {citation.section}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
              Ask what your saved knowledge says about a topic.
            </div>
          )}
        </div>
      </ScrollArea>
      <form className="flex gap-2 border-t p-4" onSubmit={submitChat}>
        <Input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="Ask your KB..." />
        <Button disabled={isChatting} type="submit">
          {isChatting ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageCircle className="h-4 w-4" />}
        </Button>
      </form>
    </Card>
  );
}

export default function App() {
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [posts, setPosts] = useState<PostRecord[]>([]);
  const [graph, setGraph] = useState<KnowledgeGraph>({ nodes: [], edges: [] });
  const [activeView, setActiveView] = useState<ActiveView>("home");
  const [notesMode, setNotesMode] = useState<NotesMode>("note");
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [selectedSourceDetail, setSelectedSourceDetail] = useState<SourceDetail | null>(null);
  const [activeType, setActiveType] = useState<SourceType>("note");
  const [title, setTitle] = useState("");
  const [noteText, setNoteText] = useState("");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatLog, setChatLog] = useState<ChatMessage[]>([]);
  const [isChatting, setIsChatting] = useState(false);

  async function refresh() {
    const [sourceResponse, postResponse, graphResponse] = await Promise.all([
      fetch(`${API_BASE_URL}/sources`),
      fetch(`${API_BASE_URL}/posts`),
      fetch(`${API_BASE_URL}/graph`),
    ]);
    if (!sourceResponse.ok || !postResponse.ok || !graphResponse.ok) {
      throw new Error("Knowledge API returned an error.");
    }
    const nextSources = (await sourceResponse.json()) as SourceRecord[];
    setSources(nextSources);
    setPosts((await postResponse.json()) as PostRecord[]);
    setGraph((await graphResponse.json()) as KnowledgeGraph);
    if (!selectedSourceId && nextSources.length) {
      setSelectedSourceId(nextSources[0].id);
    }
  }

  useEffect(() => {
    refresh().catch((error: unknown) => setNotice(errorMessage(error)));
  }, []);

  useEffect(() => {
    if (!selectedSourceId) {
      setSelectedSourceDetail(null);
      return;
    }
    fetch(`${API_BASE_URL}/sources/${selectedSourceId}`)
      .then((response) => {
        if (!response.ok) throw new Error("Source detail failed to load.");
        return response.json() as Promise<SourceDetail>;
      })
      .then(setSelectedSourceDetail)
      .catch((error: unknown) => setNotice(errorMessage(error)));
  }, [selectedSourceId]);

  async function submitSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (activeType === "youtube") {
      setNotice("Video ingestion to be fixed.");
      return;
    }
    setIsSubmitting(true);
    setNotice("");
    try {
      const formData = new FormData();
      formData.append("type", activeType);
      formData.append("title", title);
      if (activeType === "note") formData.append("text", noteText);
      if (activeType === "pdf" && pdfFile) formData.append("file", pdfFile);

      const response = await fetch(`${API_BASE_URL}/sources`, { method: "POST", body: formData });
      const payload = (await response.json()) as SourceRecord & ApiError;
      if (!response.ok) throw new Error(payload.detail || "Source ingestion failed.");
      if (payload.status === "failed") {
        setNotice(payload.error || "Source failed to process.");
      } else {
        setTitle("");
        setNoteText("");
        setYoutubeUrl("");
        setPdfFile(null);
        setSelectedSourceId(payload.id);
        setActiveView("notes");
        setNotesMode("note");
      }
      await refresh();
    } catch (error: unknown) {
      setNotice(errorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = chatInput.trim();
    if (!message) return;
    setChatInput("");
    setIsChatting(true);
    setChatLog((current) => [...current, { role: "user", text: message }]);
    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const payload = (await response.json()) as { answer: string; citations?: Citation[] } & ApiError;
      if (!response.ok) throw new Error(payload.detail || "Chat failed.");
      setChatLog((current) => [...current, { role: "assistant", text: payload.answer, citations: payload.citations || [] }]);
    } catch (error: unknown) {
      setChatLog((current) => [...current, { role: "assistant", text: errorMessage(error) }]);
    } finally {
      setIsChatting(false);
    }
  }

  const sourcesByType = useMemo(() => {
    return sources.reduce<Record<SourceType, SourceRecord[]>>(
      (groups, source) => {
        groups[source.type].push(source);
        return groups;
      },
      { note: [], pdf: [], youtube: [] },
    );
  }, [sources]);
  const readyCount = sources.filter((source) => source.status === "ready").length;
  const conceptCount = graph.nodes.filter((node) => node.type === "concept").length;
  const chatPanel = (
    <ChatPanel chatInput={chatInput} chatLog={chatLog} isChatting={isChatting} setChatInput={setChatInput} submitChat={submitChat} />
  );

  return (
    <TooltipProvider>
      <div className="app-frame pb-20 lg:pb-0">
        <TopBar />
        <div className={activeView === "home" ? "social-grid" : "notes-grid"}>
          <SidebarNav activeView={activeView} notesMode={notesMode} setActiveView={setActiveView} setNotesMode={setNotesMode} />

          {activeView === "home" ? (
            <main className="min-h-[calc(100vh-74px)] border-r">
              <div className="flex h-14 items-center justify-between border-b px-6">
                <h1 className="font-bold">Home</h1>
                <Button onClick={() => refresh().catch((error: unknown) => setNotice(errorMessage(error)))} size="icon" variant="outline">
                  <RefreshCcw className="h-4 w-4" />
                </Button>
              </div>
              <ScrollArea className="h-[calc(100vh-128px)]">
                <div className="mx-auto max-w-2xl space-y-4 p-5">
                  {notice && <div className="rounded-lg border border-destructive/25 bg-destructive/5 p-3 text-sm text-destructive">{notice}</div>}
                  {posts.length ? (
                    posts.map((post) => (
                      <Card key={post.id}>
                        <CardHeader className="flex-row gap-3 space-y-0">
                          <Avatar>
                            <AvatarFallback>{post.source_title.slice(0, 2).toUpperCase()}</AvatarFallback>
                          </Avatar>
                          <div>
                            <CardTitle className="text-base">{post.source_title}</CardTitle>
                            <CardDescription>{formatDate(post.created_at)} · AI-generated digest</CardDescription>
                          </div>
                        </CardHeader>
                        <CardContent>
                          <p className="whitespace-pre-wrap leading-7">{post.body}</p>
                        </CardContent>
                      </Card>
                    ))
                  ) : (
                    <div className="grid min-h-[58vh] place-items-center text-center">
                      <div>
                        <Sparkles className="mx-auto mb-6 h-24 w-24 text-primary" />
                        <h2 className="text-4xl font-black tracking-tight">Nothing to see yet</h2>
                        <p className="mt-3 text-lg text-muted-foreground">Digest a source and posts will appear here.</p>
                        <Button className="mt-6" onClick={() => setActiveView("digest")}>
                          <Upload className="h-4 w-4" />
                          Digest Source
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </main>
          ) : activeView === "digest" ? (
            <DigestSourcePage
              activeType={activeType}
              isSubmitting={isSubmitting}
              noteText={noteText}
              notice={notice}
              pdfFile={pdfFile}
              setActiveType={setActiveType}
              setNoteText={setNoteText}
              setPdfFile={setPdfFile}
              setTitle={setTitle}
              setYoutubeUrl={setYoutubeUrl}
              submitSource={submitSource}
              title={title}
              youtubeUrl={youtubeUrl}
            />
          ) : (
            <main className="min-h-[calc(100vh-74px)] border-r">
              <div className="flex h-14 items-center justify-between border-b px-5">
                <div>
                  <h1 className="font-bold">Notes</h1>
                  <p className="text-xs text-muted-foreground">{readyCount} ready sources · {conceptCount} concepts</p>
                </div>
                <div className="flex items-center gap-2">
                  <Tabs value={notesMode} onValueChange={(value) => setNotesMode(value as NotesMode)}>
                    <TabsList>
                      <TabsTrigger value="note">Note</TabsTrigger>
                      <TabsTrigger value="graph">Graph</TabsTrigger>
                    </TabsList>
                  </Tabs>
                  <Sheet>
                    <SheetTrigger asChild>
                      <Button className="lg:hidden" size="icon" variant="outline">
                        <Bot className="h-4 w-4" />
                      </Button>
                    </SheetTrigger>
                    <SheetContent className="flex w-[92vw] max-w-none flex-col p-0" side="right">
                      <SheetHeader className="sr-only">
                        <SheetTitle>AI Chat</SheetTitle>
                      </SheetHeader>
                      {chatPanel}
                    </SheetContent>
                  </Sheet>
                </div>
              </div>

              <div className="grid min-h-[calc(100vh-128px)] grid-cols-1 xl:grid-cols-[280px_minmax(0,1fr)]">
                <aside className="border-b bg-muted/20 xl:border-b-0 xl:border-r">
                  <ScrollArea className="h-[320px] xl:h-[calc(100vh-128px)]">
                    <div className="space-y-5 p-4">
                      <div>
                        <div className="mb-2 flex items-center gap-2 text-sm font-bold">
                          <FileText className="h-4 w-4" />
                          Vault
                        </div>
                        <div className="space-y-4">
                          {(["note", "pdf", "youtube"] as const).map((type) => (
                            <div key={type}>
                              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{type}</div>
                              <div className="space-y-1">
                                {sourcesByType[type].length ? (
                                  sourcesByType[type].map((source) => (
                                    <button
                                      className={cn(
                                        "flex w-full items-start justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-muted",
                                        selectedSourceId === source.id && "bg-muted",
                                      )}
                                      key={source.id}
                                      onClick={() => { setSelectedSourceId(source.id); setNotesMode("note"); }}
                                      type="button"
                                    >
                                      <span className="min-w-0">
                                        <span className="block truncate font-medium">{source.title}</span>
                                        <span className="text-xs text-muted-foreground">{formatDate(source.created_at)}</span>
                                      </span>
                                      <StatusBadge status={source.status} />
                                    </button>
                                  ))
                                ) : (
                                  <div className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground">No {type} sources</div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </ScrollArea>
                </aside>

                <section className="min-w-0">
                  <ScrollArea className="h-[calc(100vh-128px)]">
                    <div className="mx-auto max-w-4xl p-5">
                      {notice && <div className="mb-4 rounded-lg border border-destructive/25 bg-destructive/5 p-3 text-sm text-destructive">{notice}</div>}
                      {notesMode === "graph" ? (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between">
                            <div>
                              <h2 className="text-2xl font-black">Knowledge Graph</h2>
                              <p className="text-sm text-muted-foreground">Graphified concepts from the current knowledge base.</p>
                            </div>
                            <Button onClick={() => setNotesMode("graph")}>
                              <GitBranch className="h-4 w-4" />
                              Graphify
                            </Button>
                          </div>
                          <GraphView graph={graph} onRefresh={() => refresh().catch((error: unknown) => setNotice(errorMessage(error)))} />
                        </div>
                      ) : selectedSourceDetail ? (
                        <Card>
                          <CardHeader>
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div>
                                <CardTitle className="text-2xl">{selectedSourceDetail.title}</CardTitle>
                                <CardDescription>
                                  {selectedSourceDetail.type} · {formatDate(selectedSourceDetail.created_at)}
                                </CardDescription>
                              </div>
                              <StatusBadge status={selectedSourceDetail.status} />
                            </div>
                            {selectedSourceDetail.error && <p className="text-sm text-destructive">{selectedSourceDetail.error}</p>}
                          </CardHeader>
                          <Separator />
                          <CardContent className="pt-5">
                            <MarkdownView markdown={selectedSourceDetail.markdown} />
                          </CardContent>
                        </Card>
                      ) : (
                        <Card className="grid min-h-[420px] place-items-center border-dashed">
                          <CardContent className="pt-6 text-center">
                            <BookOpen className="mx-auto mb-4 h-10 w-10 text-muted-foreground" />
                            <p className="font-semibold">Select a note</p>
                            <p className="mt-1 text-sm text-muted-foreground">Digest a source or choose one from the vault.</p>
                          </CardContent>
                        </Card>
                      )}
                    </div>
                  </ScrollArea>
                </section>
              </div>
            </main>
          )}

          {activeView === "home" ? (
            <aside className="sticky top-[74px] hidden h-[calc(100vh-74px)] space-y-5 bg-background p-6 lg:block">
              <Card>
                <CardHeader>
                  <CardTitle>Trendings</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-lg font-semibold">
                  <div># KnowledgeGraph</div>
                  <div># PersonalAI</div>
                  <div># DigestNotes</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Vault Suggestions</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {sources.slice(0, 3).map((source) => (
                    <div className="flex items-center justify-between gap-3" key={source.id}>
                      <div className="flex min-w-0 items-center gap-3">
                        <Avatar>
                          <AvatarFallback>{source.title.slice(0, 2).toUpperCase()}</AvatarFallback>
                        </Avatar>
                        <div className="min-w-0">
                          <div className="truncate font-semibold">{source.title}</div>
                          <div className="text-sm text-muted-foreground">@{source.type}</div>
                        </div>
                      </div>
                      <Button onClick={() => { setSelectedSourceId(source.id); setActiveView("notes"); }} size="sm" variant="outline">
                        View
                      </Button>
                    </div>
                  ))}
                  {!sources.length && <p className="text-sm text-muted-foreground">Digest sources to get suggestions.</p>}
                </CardContent>
              </Card>
              <p className="px-2 text-sm font-medium text-muted-foreground">2026 Second Signal · Personal knowledge feed</p>
            </aside>
          ) : (
            <aside className="sticky top-[74px] hidden h-[calc(100vh-74px)] lg:block">{chatPanel}</aside>
          )}
        </div>
        <MobileNav activeView={activeView} setActiveView={setActiveView} />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button className="fixed bottom-20 right-4 z-40 rounded-full shadow-lg lg:hidden" onClick={() => { setActiveView("notes"); setNotesMode("graph"); }} size="icon">
              <GitBranch className="h-5 w-5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Graphify</TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  );
}
