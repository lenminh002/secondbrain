import { useEffect, useState } from "react";
import { BookOpen, FileText, Pencil, ChevronLeft, ChevronRight } from "lucide-react";

import { GraphView } from "@/components/GraphView";
import { SourceContent } from "@/components/SourceContent";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

import { updateSourceContent } from "@/lib/api";
import { cn } from "@/lib/utils";
import { errorMessage, formatDate } from "@/lib/format";
import type { KnowledgeGraph, NotesMode, SourceDetail, SourceRecord, SourceType } from "@/types";

export function NotesView({
  chatPanel,
  conceptCount,
  graph,
  notesMode,
  notice,
  readyCount,
  refreshKnowledge,
  selectedSourceDetail,
  selectedSourceId,
  setNotice,
  setNotesMode,
  setSelectedSourceId,
  setSelectedSourceDetail,
  sourcesByType,
}: {
  chatPanel: React.ReactNode;
  conceptCount: number;
  graph: KnowledgeGraph;
  notesMode: NotesMode;
  notice: string;
  readyCount: number;
  refreshKnowledge: () => Promise<void>;
  selectedSourceDetail: SourceDetail | null;
  selectedSourceId: string | null;
  setNotice: (notice: string) => void;
  setNotesMode: (mode: NotesMode) => void;
  setSelectedSourceId: (id: string) => void;
  setSelectedSourceDetail: (source: SourceDetail) => void;
  sourcesByType: Record<SourceType, SourceRecord[]>;
}) {
  const [isVaultMinimized, setIsVaultMinimized] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [draftContent, setDraftContent] = useState("");

  const selectedContent = selectedSourceDetail?.content ?? "";
  const canEdit = selectedSourceDetail?.status === "ready";
  const saveDisabled = (
    isSaving
    || !draftContent.trim()
    || draftContent.trim() === selectedContent.trim()
  );

  useEffect(() => {
    setIsEditing(false);
    setIsSaving(false);
    setDraftContent(selectedSourceDetail?.content ?? "");
  }, [selectedSourceDetail?.id]);

  function startEditing() {
    setDraftContent(selectedContent);
    setIsEditing(true);
  }

  function cancelEditing() {
    setDraftContent(selectedContent);
    setIsEditing(false);
  }

  async function saveEdit() {
    if (!selectedSourceDetail || saveDisabled) return;
    setIsSaving(true);
    try {
      const updatedSource = await updateSourceContent(selectedSourceDetail.id, draftContent);
      setSelectedSourceDetail(updatedSource);
      await refreshKnowledge();
      setNotice("");
      setIsEditing(false);
      setDraftContent(updatedSource.content ?? "");
    } catch (error: unknown) {
      setNotice(errorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <main className="min-h-[calc(100vh-74px)] min-w-0 border-r @container">
      <div
        className={cn(
          "grid h-[calc(100vh-74px)] transition-[grid-template-columns] duration-300",
          notesMode === "graph"
            ? "grid-cols-1"
            : "grid-cols-1 @2xl:grid-cols-[var(--vault-width,280px)_minmax(0,1fr)]"
        )}
        style={{ "--vault-width": isVaultMinimized ? "48px" : "280px" } as React.CSSProperties}
      >
        {notesMode !== "graph" && (
          <aside className="min-h-0 border-b bg-muted/20 @2xl:border-b-0 @2xl:border-r relative transition-all duration-300">
            {isVaultMinimized ? (
              <div className="flex flex-col items-center py-4 h-full">
                <Button variant="ghost" size="icon" onClick={() => setIsVaultMinimized(false)}>
                  <ChevronRight className="h-5 w-5" />
                </Button>
                <FileText className="h-5 w-5 mt-4 text-muted-foreground" />
              </div>
            ) : (
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute top-2 right-2 z-10 h-8 w-8 hidden @2xl:flex"
                  onClick={() => setIsVaultMinimized(true)}
                >
                  <ChevronLeft className="h-4 w-4 text-muted-foreground" />
                </Button>
                <ScrollArea className="h-full max-h-[320px] @2xl:max-h-none">
                  <div className="space-y-5 p-4">
                    <div>
                      <div className="flex items-center gap-2 text-lg font-bold">
                        <FileText className="h-6 w-6" />
                        Vault
                      </div>
                      <div className="space-y-4 mt-6">
                        {(["note", "pdf"] as const).map((type) => (
                          <div key={type}>
                            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{type}</div>
                            <div className="space-y-1">
                              {sourcesByType[type].length ? (
                                sourcesByType[type].map((source) => (
                                  <button
                                    className={cn(
                                      "w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-muted",
                                      selectedSourceId === source.id && "bg-muted",
                                    )}
                                    key={source.id}
                                    onClick={() => { setSelectedSourceId(source.id); setNotesMode("note"); }}
                                    type="button"
                                  >
                                    <span className="flex w-full items-start justify-between gap-2 min-w-0">
                                      <span className="min-w-0">
                                        <span className="block truncate font-medium">{source.title}</span>
                                        <span className="text-xs text-muted-foreground">{formatDate(source.created_at)}</span>
                                      </span>
                                      <StatusBadge status={source.status} />
                                    </span>
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
              </>
            )}
          </aside>
        )}

        <section className="min-h-0 min-w-0">
          <ScrollArea className="h-full">
            <div className="mx-auto max-w-4xl p-5">
              {notice && <div className="mb-4 rounded-lg border border-destructive/25 bg-destructive/5 p-3 text-sm text-destructive break-words">{notice}</div>}
              {notesMode === "graph" ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-2xl font-black">Knowledge Graph</h2>
                      <p className="text-sm text-muted-foreground">Graphified concepts from the current knowledge base.</p>
                    </div>

                  </div>
                  <GraphView graph={graph} onRefresh={() => { void refreshKnowledge(); }} />
                </div>
              ) : selectedSourceDetail ? (
                <Card>
                  <CardHeader>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <CardTitle className="text-2xl break-words">{selectedSourceDetail.title}</CardTitle>
                        <CardDescription>
                          {selectedSourceDetail.type} · {formatDate(selectedSourceDetail.created_at)}
                        </CardDescription>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge status={selectedSourceDetail.status} />
                        {isEditing ? (
                          <>
                            <Button
                              disabled={isSaving}
                              onClick={cancelEditing}
                              size="sm"
                              type="button"
                              variant="outline"
                            >
                              Cancel
                            </Button>
                            <Button
                              disabled={saveDisabled}
                              onClick={() => { void saveEdit(); }}
                              size="sm"
                              type="button"
                            >
                              {isSaving ? "Saving..." : "Save"}
                            </Button>
                          </>
                        ) : canEdit ? (
                          <Button onClick={startEditing} size="sm" type="button" variant="outline">
                            <Pencil className="h-4 w-4" />
                            Edit
                          </Button>
                        ) : null}
                      </div>
                    </div>
                    {selectedSourceDetail.error && <p className="text-sm text-destructive break-words">{selectedSourceDetail.error}</p>}
                  </CardHeader>
                  <Separator />
                  <CardContent className="pt-5">
                    <SourceContent
                      draftContent={draftContent}
                      isEditing={isEditing}
                      isSaving={isSaving}
                      onDraftContentChange={setDraftContent}
                      source={selectedSourceDetail}
                    />
                  </CardContent>
                </Card>
              ) : (
                <Card className="grid min-h-[420px] place-items-center border-dashed">
                  <CardContent className="pt-6 text-center">
                    <BookOpen className="mx-auto mb-4 h-10 w-10 text-muted-foreground" />
                    <p className="font-semibold">Select a note</p>
                    <p className="mt-1 text-sm text-muted-foreground">Ingest a source or choose one from the vault.</p>
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
