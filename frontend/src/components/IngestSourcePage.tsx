import { FormEvent } from "react";
import { CheckCircle2, Loader2, Sparkles, Upload } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import type { SourceRecord, SourceType } from "@/types";

function sourceTypeLabel(type: SourceType) {
  if (type === "pdf") return "PDF";
  if (type === "youtube") return "Video";
  return "Note";
}

export function IngestSourcePage({
  activeType,
  ingestProgress,
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
  ingestProgress: SourceRecord | null;
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
  const progressPercent = Math.min(100, Math.max(0, ingestProgress?.progress_percent ?? 0));
  const progressType = ingestProgress?.type ?? activeType;
  const progressTitle = ingestProgress?.status === "failed"
    ? `${sourceTypeLabel(progressType)} ingestion stopped`
    : `Ingesting ${sourceTypeLabel(progressType)}`;

  return (
    <main className="min-h-[calc(100vh-74px)] border-r">
      <div className="flex h-14 items-center justify-between border-b px-6">
        <div>
          <h1 className="font-bold">Ingest Source</h1>
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
                The ingest pipeline creates structured source records, generated posts, chunks, embeddings, and graph nodes.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-5">
              <form className="space-y-5" onSubmit={submitSource}>
                <Tabs value={activeType} onValueChange={(value) => { if (!isSubmitting) setActiveType(value as SourceType); }}>
                  <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger disabled={isSubmitting} value="note">Note</TabsTrigger>
                    <TabsTrigger disabled={isSubmitting} value="pdf">PDF</TabsTrigger>
                    <TabsTrigger disabled value="youtube">Video</TabsTrigger>
                  </TabsList>
                </Tabs>
                <p className="text-xs text-muted-foreground">Video ingestion to be fixed.</p>

                <div className="space-y-2">
                  <label className="text-sm font-semibold" htmlFor="ingest-title">Title</label>
                  <Input disabled={isSubmitting} id="ingest-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Research paper, lecture, book chapter..." />
                </div>

                {activeType === "note" && (
                  <div className="space-y-2">
                    <label className="text-sm font-semibold" htmlFor="ingest-note">Notes</label>
                    <Textarea
                      disabled={isSubmitting}
                      id="ingest-note"
                      value={noteText}
                      onChange={(event) => setNoteText(event.target.value)}
                      placeholder="Paste highlights, rough notes, or ideas you consumed."
                      rows={14}
                    />
                  </div>
                )}

                {activeType === "pdf" && (
                  <div className="space-y-2">
                    <label className="text-sm font-semibold" htmlFor="ingest-pdf">PDF</label>
                    <Input disabled={isSubmitting} id="ingest-pdf" accept="application/pdf" type="file" onChange={(event) => setPdfFile(event.target.files?.[0] || null)} />
                    <p className="text-xs text-muted-foreground">{pdfFile ? `${pdfFile.name} selected` : "Upload a readable PDF with selectable text."}</p>
                  </div>
                )}

                {activeType === "youtube" && (
                  <div className="space-y-2">
                    <label className="text-sm font-semibold" htmlFor="ingest-youtube">YouTube URL</label>
                    <Input disabled={isSubmitting} id="ingest-youtube" value={youtubeUrl} onChange={(event) => setYoutubeUrl(event.target.value)} placeholder="https://youtube.com/watch?v=..." />
                    <p className="text-xs text-muted-foreground">MVP uses available captions/transcripts only.</p>
                  </div>
                )}

                {ingestProgress && (
                  <div className="rounded-lg border bg-muted/30 p-4" aria-live="polite">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-bold">{progressTitle}</p>
                        <p className="text-xs text-muted-foreground">{ingestProgress.progress_label || "Starting ingestion"}</p>
                      </div>
                      <Badge variant="secondary">{progressPercent}%</Badge>
                    </div>
                    <div
                      aria-label="Ingestion progress"
                      aria-valuemax={100}
                      aria-valuemin={0}
                      aria-valuenow={progressPercent}
                      className="h-2 overflow-hidden rounded-full bg-secondary"
                      role="progressbar"
                    >
                      <div
                        className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
                        style={{ width: `${progressPercent}%` }}
                      />
                    </div>
                  </div>
                )}

                {notice && <div className="rounded-lg border border-destructive/25 bg-destructive/5 p-3 text-sm text-destructive break-words">{notice}</div>}

                <Button className="h-11 w-full" disabled={isSubmitting} type="submit">
                  {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                  {isSubmitting ? "Ingesting source..." : "Ingest source"}
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
                <p>2. Normalize it into structured memory fields.</p>
                <p>3. Generate summary, concepts, claims, and a social post.</p>
                <p>4. Add chunks to retrieval and concepts to the graph.</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Output surfaces</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                <Badge variant="secondary">Memories vault</Badge>
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
