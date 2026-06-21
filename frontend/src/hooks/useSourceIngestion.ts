import { FormEvent, useState } from "react";
import { createSource, fetchSourceDetail } from "@/lib/api";
import { errorMessage } from "@/lib/format";
import type { ActiveView, NotesMode, SourceRecord, SourceDetail, SourceType } from "@/types";

const INGEST_POLL_INTERVAL_MS = 750;

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

interface UseSourceIngestionProps {
  refresh: () => Promise<void>;
  setSelectedSourceId: (id: string | null) => void;
  setActiveView: (view: ActiveView) => void;
  setNotesMode: (mode: NotesMode) => void;
  setNotice: (msg: string) => void;
}

export function useSourceIngestion({
  refresh,
  setSelectedSourceId,
  setActiveView,
  setNotesMode,
  setNotice,
}: UseSourceIngestionProps) {
  const [activeType, setActiveType] = useState<SourceType>("note");
  const [title, setTitle] = useState("");
  const [noteText, setNoteText] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [ingestProgress, setIngestProgress] = useState<SourceRecord | null>(null);

  async function submitSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    setIngestProgress(null);
    setNotice("");
    try {
      const formData = new FormData();
      formData.append("type", activeType);
      formData.append("title", title);
      if (activeType === "note") formData.append("text", noteText);
      if (activeType === "pdf" && pdfFile) formData.append("file", pdfFile);

      const payload = await createSource(formData);
      setIngestProgress(payload);

      let completedSource: SourceRecord | SourceDetail = payload;
      while (completedSource.status === "processing") {
        await wait(INGEST_POLL_INTERVAL_MS);
        completedSource = await fetchSourceDetail(payload.id);
        setIngestProgress(completedSource);
      }

      if (completedSource.status === "failed") {
        setNotice(completedSource.error || "Source failed to process.");
        await refresh();
      } else {
        setTitle("");
        setNoteText("");
        setPdfFile(null);
        await refresh();
        setSelectedSourceId(completedSource.id);
        setActiveView("notes");
        setNotesMode("note");
        setIngestProgress(null);
      }
    } catch (error: unknown) {
      setNotice(errorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  return {
    activeType,
    setActiveType,
    title,
    setTitle,
    noteText,
    setNoteText,
    pdfFile,
    setPdfFile,
    isSubmitting,
    setIsSubmitting,
    ingestProgress,
    setIngestProgress,
    submitSource,
  };
}
