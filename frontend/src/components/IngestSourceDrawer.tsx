import { FormEvent } from "react";
import { Loader2, Upload, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import type { SourceRecord, SourceType } from "@/types";

function sourceTypeLabel(type: SourceType) {
  if (type === "pdf") return "PDF";
  return "Note";
}

interface IngestSourceDrawerProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
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
  submitSource: (event: FormEvent<HTMLFormElement>) => void;
  title: string;
}

export function IngestSourceDrawer({
  isOpen,
  onOpenChange,
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
  submitSource,
  title,
}: IngestSourceDrawerProps) {
  const progressPercent = Math.min(100, Math.max(0, ingestProgress?.progress_percent ?? 0));
  const progressType = ingestProgress?.type ?? activeType;
  const progressTitle = ingestProgress?.status === "failed"
    ? `${sourceTypeLabel(progressType)} ingestion stopped`
    : `Ingesting ${sourceTypeLabel(progressType)}`;

  return (
    <Drawer open={isOpen} onOpenChange={onOpenChange}>
      <DrawerContent className="bg-background max-h-[90vh]">
        <div className="mx-auto w-full max-w-2xl overflow-y-auto px-4 pb-6">
          <DrawerHeader className="relative border-b pb-4">
            <div className="text-left">
              <DrawerTitle className="text-xl font-bold flex items-center gap-2">
                <Upload className="h-5 w-5" />
                Ingest Source
              </DrawerTitle>
              <DrawerDescription>
                Turn notes and papers into structured memory for your knowledge base.
              </DrawerDescription>
            </div>
            <DrawerClose asChild>
              <Button variant="ghost" size="icon" className="absolute right-0 top-0">
                <X className="h-4 w-4" />
              </Button>
            </DrawerClose>
          </DrawerHeader>

          <div className="grid gap-6 pt-5 md:grid-cols-[1fr_240px]">
            <form className="space-y-4" onSubmit={submitSource}>
              <Tabs
                value={activeType}
                onValueChange={(value) => {
                  if (!isSubmitting) setActiveType(value as SourceType);
                }}
              >
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger disabled={isSubmitting} value="note">
                    Note
                  </TabsTrigger>
                  <TabsTrigger disabled={isSubmitting} value="pdf">
                    PDF
                  </TabsTrigger>
                </TabsList>
              </Tabs>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground" htmlFor="ingest-title">
                  Title
                </label>
                <Input
                  disabled={isSubmitting}
                  id="ingest-title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Research paper, lecture, book chapter..."
                />
              </div>

              {activeType === "note" && (
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground" htmlFor="ingest-note">
                    Notes
                  </label>
                  <Textarea
                    disabled={isSubmitting}
                    id="ingest-note"
                    value={noteText}
                    onChange={(event) => setNoteText(event.target.value)}
                    placeholder="Paste highlights, rough notes, or ideas you consumed."
                    rows={8}
                  />
                </div>
              )}

              {activeType === "pdf" && (
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-muted-foreground" htmlFor="ingest-pdf">
                    PDF File
                  </label>
                  <Input
                    disabled={isSubmitting}
                    id="ingest-pdf"
                    accept="application/pdf"
                    type="file"
                    onChange={(event) => setPdfFile(event.target.files?.[0] || null)}
                  />
                  <p className="text-xs text-muted-foreground">
                    {pdfFile ? `${pdfFile.name} selected` : "Upload a readable PDF with selectable text."}
                  </p>
                </div>
              )}

              {ingestProgress && (
                <div className="rounded-lg border bg-muted/20 p-3" aria-live="polite">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-bold">{progressTitle}</p>
                      <p className="text-[10px] text-muted-foreground">
                        {ingestProgress.progress_label || "Starting ingestion"}
                      </p>
                    </div>
                    <Badge variant="secondary" className="text-[10px]">
                      {progressPercent}%
                    </Badge>
                  </div>
                  <div
                    aria-label="Ingestion progress"
                    aria-valuemax={100}
                    aria-valuemin={0}
                    aria-valuenow={progressPercent}
                    className="h-1.5 overflow-hidden rounded-full bg-secondary"
                    role="progressbar"
                  >
                    <div
                      className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </div>
              )}

              {notice && (
                <div className="rounded-lg border border-destructive/25 bg-destructive/5 p-3 text-xs text-destructive break-words">
                  {notice}
                </div>
              )}

              <Button className="h-10 w-full" disabled={isSubmitting} type="submit">
                {isSubmitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="h-4 w-4" />
                )}
                {isSubmitting ? "Ingesting source..." : "Ingest source"}
              </Button>
            </form>
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
