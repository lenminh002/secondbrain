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

export function SourceContent({ source }: { source: SourceDetail }) {
  return (
    <div className="space-y-2">
      {source.summary && (
        <Section title="Summary">
          <p className="text-sm leading-relaxed">{source.summary}</p>
        </Section>
      )}

      {source.key_ideas?.length > 0 && (
        <Section title="Key Ideas">
          <BulletList items={source.key_ideas} />
        </Section>
      )}

      {source.content && (
        <Section title="Notes">
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{source.content}</p>
        </Section>
      )}

      {source.concepts?.length > 0 && (
        <Section title="Concepts">
          <BulletList items={source.concepts} />
        </Section>
      )}

      {source.claims?.length > 0 && (
        <Section title="Claims">
          <BulletList items={source.claims} />
        </Section>
      )}

      {source.questions?.length > 0 && (
        <Section title="Questions">
          <BulletList items={source.questions} />
        </Section>
      )}
    </div>
  );
}
