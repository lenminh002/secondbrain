import { RefreshCcw, Sparkles, Upload } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatDate } from "@/lib/format";
import type { AccountRecord, ActiveView, PostRecord, SourceRecord } from "@/types";

export function HomeView({
  account,
  notice,
  posts,
  refresh,
  setActiveView,
}: {
  account: AccountRecord | null;
  notice: string;
  posts: PostRecord[];
  refresh: () => void;
  setActiveView: (view: ActiveView) => void;
}) {
  return (
    <main className="min-h-[calc(100vh-74px)] border-r">
      <div className="flex h-14 items-center justify-between border-b px-6">
        <h1 className="font-bold">Home</h1>
        <Button onClick={refresh} size="icon" variant="outline">
          <RefreshCcw className="h-4 w-4" />
        </Button>
      </div>
      <ScrollArea className="h-[calc(100vh-128px)]">
        <div className="mx-auto max-w-2xl space-y-4 p-5">
          {notice && <div className="rounded-lg border border-destructive/25 bg-destructive/5 p-3 text-sm text-destructive">{notice}</div>}
          {posts.length ? (
            posts.map((post) => (
              <Card key={post.id}>
                <CardHeader className="flex-row gap-3 space-y-0">
                  <Avatar>
                    {account?.avatar_url && <AvatarImage alt={account.name} src={account.avatar_url} />}
                    <AvatarFallback>{account?.initials || ""}</AvatarFallback>
                  </Avatar>
                  <div>
                    <CardTitle className="text-base">{post.source_title}</CardTitle>
                    <CardDescription>
                      @{account?.handle || post.account_id} ·{" "}
                      {formatDate(post.created_at)}
                    </CardDescription>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="whitespace-pre-wrap leading-7">{post.body}</p>
                </CardContent>
              </Card>
            ))
          ) : (
            <div className="grid min-h-[58vh] place-items-center text-center">
              <div>
                <Sparkles className="mx-auto mb-6 h-24 w-24 text-primary" />
                <h2 className="text-4xl font-black tracking-tight">Nothing to see yet</h2>
                <p className="mt-3 text-lg text-muted-foreground">Digest a source and posts will appear here.</p>
                <Button className="mt-6" onClick={() => setActiveView("digest")}>
                  <Upload className="h-4 w-4" />
                  Digest Source
                </Button>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
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
          <div># DigestNotes</div>
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
          {!sources.length && <p className="text-sm text-muted-foreground">Digest sources to get suggestions.</p>}
        </CardContent>
      </Card>
      <p className="px-2 text-sm font-medium text-muted-foreground">2026 {account?.name || "Profile"} · Personal knowledge feed</p>
    </aside>
  );
}
