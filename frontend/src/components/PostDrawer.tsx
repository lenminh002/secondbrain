import { FormEvent, useState } from "react";
import { FileText, Files, Link2, Loader2, Plus, Video } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@/components/ui/drawer";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { createSource } from "@/lib/api";
import { errorMessage } from "@/lib/format";

// "youtube" (Video) is shown as a disabled tab for the demo and is not selectable.
type DraftType = "link" | "note" | "pdf";

export function PostDrawer({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<DraftType>("link");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [link, setLink] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function reset() {
    setType("link");
    setTitle("");
    setText("");
    setLink("");
    setFile(null);
    setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("type", type);
      formData.append("title", title);
      if (type === "note") formData.append("text", text);
      if (type === "link") formData.append("source_url", link.trim());
      if (type === "pdf" && file) formData.append("file", file);

      await createSource(formData);
      reset();
      setOpen(false);
      onCreated();
    } catch (err: unknown) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit =
    type === "note"
      ? Boolean(title.trim() && text.trim())
      : type === "pdf"
        ? Boolean(title.trim() && file)
        : Boolean(link.trim());

  return (
    <Drawer
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DrawerTrigger asChild>
        <Button className="w-full gap-2">
          <Plus className="h-4 w-4" />
          New Post
        </Button>
      </DrawerTrigger>
      <DrawerContent className="max-h-[90vh]">
        <div className="mx-auto flex w-full max-w-2xl flex-col overflow-y-auto px-4 pb-6">
          <DrawerHeader className="px-0">
            <DrawerTitle>Create</DrawerTitle>
          </DrawerHeader>

          <form className="space-y-4" onSubmit={submit}>
          <Tabs onValueChange={(value) => setType(value as DraftType)} value={type}>
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="link">
                <Link2 className="mr-2 h-4 w-4" />
                Link
              </TabsTrigger>
              <TabsTrigger value="note">
                <FileText className="mr-2 h-4 w-4" />
                Note
              </TabsTrigger>
              <TabsTrigger value="pdf">
                <Files className="mr-2 h-4 w-4" />
                Docs
              </TabsTrigger>
              <TabsTrigger disabled title="Coming soon" value="youtube">
                <Video className="mr-2 h-4 w-4" />
                Video
              </TabsTrigger>
            </TabsList>
          </Tabs>

          <Input onChange={(event) => setTitle(event.target.value)} placeholder="Title" value={title} />

          {type === "note" ? (
            <Textarea
              className="min-h-[200px]"
              onChange={(event) => setText(event.target.value)}
              placeholder="Write your note..."
              value={text}
            />
          ) : type === "link" ? (
            <Input
              onChange={(event) => setLink(event.target.value)}
              placeholder="https://example.com/article"
              type="url"
              value={link}
            />
          ) : (
            <input
              accept="application/pdf"
              className="block w-full rounded-md bg-muted p-3 text-sm text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-primary-foreground"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              type="file"
            />
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}

          <Button className="w-full gap-2" disabled={submitting || !canSubmit} type="submit">
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            {submitting ? "Creating..." : "Create"}
          </Button>
          </form>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
