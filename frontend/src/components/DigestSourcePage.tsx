import { FormEvent } from "react";
import { CheckCircle2, Loader2, Sparkles, Upload } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import type { SourceType } from "@/types";

export function DigestSourcePage({
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
                The digest pipeline creates structured source records, generated posts, chunks, embeddings, and graph nodes.
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
