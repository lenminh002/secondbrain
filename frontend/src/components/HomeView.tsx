import { RefreshCcw, Sparkles, Upload } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AccountRecord, ActiveView, PostRecord, SourceRecord } from "@/types";

export function HomeView({
  account,
  notice,
  posts,
  refresh,
  setActiveView,
  onIngestClick,
  isLoading,
}: {
  account: AccountRecord | null;
  notice: string;
  posts: PostRecord[];
  refresh: () => void;
  setActiveView: (view: ActiveView) => void;
  onIngestClick: () => void;
  isLoading?: boolean;
}) {
  return (
    <main className="min-h-[calc(100vh-74px)]">
      <div className="h-[calc(100vh-128px)] overflow-y-auto no-scrollbar">
        <div className="flex h-14 items-center justify-between px-6">
          <h1 className="font-bold">Home</h1>
          <Button onClick={refresh} size="icon" variant="outline" disabled={isLoading}>
            <RefreshCcw className={cn("h-4 w-4", isLoading && "animate-spin")} />
          </Button>
        </div>
        <div className="mx-auto max-w-2xl space-y-4 p-5">
          {notice && <div className="rounded-lg border border-destructive/25 bg-destructive/5 p-3 text-sm text-destructive break-words">{notice}</div>}
          {isLoading ? (
            <div className="space-y-4">
              {[1, 2].map((i) => (
                <Card key={i} className="animate-pulse">
                  <CardHeader className="flex-row gap-3 space-y-0">
                    <div className="h-10 w-10 rounded-full bg-muted" />
                    <div className="space-y-2">
                      <div className="h-4 w-32 rounded bg-muted" />
                      <div className="h-3 w-20 rounded bg-muted" />
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="h-6 w-3/4 rounded bg-muted" />
                    <div className="h-40 w-full rounded-lg bg-muted" />
                    <div className="space-y-2">
                      <div className="h-4 w-full rounded bg-muted" />
                      <div className="h-4 w-5/6 rounded bg-muted" />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : posts.length ? (
            posts.map((post) => (
              <Card key={post.id}>
                <CardHeader className="flex-row gap-3 space-y-0">
                  <Avatar>
                    {account?.avatar_url && <AvatarImage alt={account.name} src={account.avatar_url} />}
                    <AvatarFallback>{account?.initials || ""}</AvatarFallback>
                  </Avatar>
                  <div>
                    <CardTitle className="text-base">Second Brain AI Agent</CardTitle>
                    <CardDescription>
                      {formatDate(post.created_at)}
                    </CardDescription>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <h3 className="font-bold">{post.source_title}</h3>
                  {post.thumbnail_url && (
                    <div className="overflow-hidden rounded-lg border max-h-72 flex items-center justify-center bg-muted/20">
                      <img
                        alt={post.source_title}
                        src={post.thumbnail_url}
                        className="w-full object-cover max-h-72"
                      />
                    </div>
                  )}
                  <div
                    className="prose prose-sm dark:prose-invert max-w-none [&_*]:text-inherit text-current"
                    data-add-to-chat-surface="true"
                  >
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {post.body}
                    </ReactMarkdown>
                  </div>
                </CardContent>
              </Card>
            ))
          ) : (
            <div className="grid min-h-[58vh] place-items-center text-center">
              <div>
                <Sparkles className="mx-auto mb-6 h-24 w-24 text-primary" />
                <h2 className="text-4xl font-black tracking-tight">Nothing to see yet</h2>
                <p className="mt-3 text-lg text-muted-foreground">Ingest a source and posts will appear here.</p>
                <Button className="mt-6" onClick={onIngestClick}>
                  <Upload className="h-4 w-4" />
                  Ingest Source
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

export function HomeAside({
  account,
  setActiveView,
  setSelectedSourceId,
  sources,
}: {
  account: AccountRecord | null;
  setActiveView: (view: ActiveView) => void;
  setSelectedSourceId: (id: string) => void;
  sources: SourceRecord[];
}) {
  return (
    <aside className="sticky top-[74px] hidden h-[calc(100vh-74px)] space-y-5 bg-background p-6 lg:block">
      <Card>
        <CardHeader>
          <CardTitle>Trendings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-lg font-semibold">
          <div># KnowledgeGraph</div>
          <div># PersonalAI</div>
          <div># IngestMemories</div>
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
          {!sources.length && <p className="text-sm text-muted-foreground">Ingest sources to get suggestions.</p>}
        </CardContent>
      </Card>
      <p className="px-2 text-sm font-medium text-muted-foreground">2026 {account?.name || "Second Brain"} · Personal knowledge feed</p>
    </aside>
  );
}
