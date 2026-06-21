import { BookOpen, Bot, FileText, GitBranch } from "lucide-react";

import { GraphView } from "@/components/GraphView";
import { SourceContent } from "@/components/SourceContent";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { formatDate } from "@/lib/format";
import type { KnowledgeGraph, NotesMode, SourceDetail, SourceRecord, SourceType } from "@/types";

export function NotesView({
  chatPanel,
  conceptCount,
  graph,
  notesMode,
  notice,
  readyCount,
  refreshGraph,
  selectedSourceDetail,
  selectedSourceId,
  setNotesMode,
  setSelectedSourceId,
  sourcesByType,
}: {
  chatPanel: React.ReactNode;
  conceptCount: number;
  graph: KnowledgeGraph;
  notesMode: NotesMode;
  notice: string;
  readyCount: number;
  refreshGraph: () => void;
  selectedSourceDetail: SourceDetail | null;
  selectedSourceId: string | null;
  setNotesMode: (mode: NotesMode) => void;
  setSelectedSourceId: (id: string) => void;
  sourcesByType: Record<SourceType, SourceRecord[]>;
}) {
  return (
    <main className="min-h-[calc(100vh-74px)] border-r @container">
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

      <div className="grid h-[calc(100vh-128px)] grid-cols-1 @2xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="min-h-0 border-b bg-muted/20 @2xl:border-b-0 @2xl:border-r">
          <ScrollArea className="h-full max-h-[320px] @2xl:max-h-none">
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

        <section className="min-h-0 min-w-0">
          <ScrollArea className="h-full">
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
                  <GraphView graph={graph} onRefresh={refreshGraph} />
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
                    <SourceContent source={selectedSourceDetail} />
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
  );
}
