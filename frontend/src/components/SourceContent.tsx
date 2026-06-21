import { ExternalLink } from "lucide-react";

import { Textarea } from "@/components/ui/textarea";
import type { SourceDetail } from "@/types";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6">
      <h2 className="mb-2 text-lg font-bold">{title}</h2>
      {children}
    </div>
  );
}

function BulletList({ items }: { items: string[] }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">None captured.</p>;
  return (
    <ul className="space-y-1 pl-4">
      {items.map((item, i) => (
        <li key={i} className="list-disc text-sm">
          {item}
        </li>
      ))}
    </ul>
  );
}

export function SourceContent({
  draftContent,
  isEditing,
  isSaving,
  onDraftContentChange,
  source,
}: {
  draftContent?: string;
  isEditing?: boolean;
  isSaving?: boolean;
  onDraftContentChange?: (content: string) => void;
  source: SourceDetail;
}) {
  const originalFile = source.metadata?.original_file;
  const originalFileLink = originalFile?.drive_web_view_link || source.source_url;

  return (
    <div className="space-y-2">
      {originalFileLink && (
        <Section title="Original File">
          <a
            className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-semibold hover:bg-muted"
            href={originalFileLink}
            rel="noreferrer"
            target="_blank"
          >
            <ExternalLink className="h-4 w-4" />
            Open original PDF
          </a>
          {originalFile?.filename && (
            <p className="mt-2 text-xs text-muted-foreground">{originalFile.filename}</p>
          )}
        </Section>
      )}

      {source.summary && (
        <Section title="Summary">
          <p className="text-sm leading-relaxed">{source.summary}</p>
        </Section>
      )}

      {!!source.key_ideas?.length && (
        <Section title="Key Ideas">
          <BulletList items={source.key_ideas} />
        </Section>
      )}

      {(source.content || isEditing) && (
        <Section title="Notes">
          {isEditing ? (
            <Textarea
              className="min-h-[260px] resize-y leading-relaxed"
              disabled={isSaving}
              onChange={(event) => onDraftContentChange?.(event.target.value)}
              value={draftContent ?? ""}
            />
          ) : (
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{source.content}</p>
          )}
        </Section>
      )}

      {!!source.concepts?.length && (
        <Section title="Concepts">
          <BulletList items={source.concepts} />
        </Section>
      )}

      {!!source.claims?.length && (
        <Section title="Claims">
          <BulletList items={source.claims} />
        </Section>
      )}

      {!!source.questions?.length && (
        <Section title="Questions">
          <BulletList items={source.questions} />
        </Section>
      )}
    </div>
  );
}
