import { AtSign, BadgeCheck, Bug, CalendarDays, FileText, Grid2X2, Repeat2, Tag, Upload } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatDate } from "@/lib/format";
import type { AccountRecord, ActiveView, PostRecord, SourceRecord } from "@/types";

export function ProfileView({
  account,
  conceptCount,
  posts,
  readyCount,
  setActiveView,
  sources,
}: {
  account: AccountRecord | null;
  conceptCount: number;
  posts: PostRecord[];
  readyCount: number;
  setActiveView: (view: ActiveView) => void;
  sources: SourceRecord[];
}) {
  return (
    <main className="min-h-[calc(100vh-74px)] border-r bg-background">
      <ScrollArea className="h-[calc(100vh-74px)]">
        <section className="relative border-b">
          <div className="grid min-h-40 place-items-center bg-muted px-6 text-center md:min-h-52">
            <h1 className="text-3xl font-bold tracking-tight md:text-5xl">
              2026 {account?.name || "Profile"}
            </h1>
          </div>
          <div className="px-5 pb-6">
            <div className="-mt-12 flex h-28 w-28 items-center justify-center rounded-full border-4 border-background bg-slate-100 shadow-sm md:-mt-16 md:h-36 md:w-36">
              <Avatar className="h-full w-full">
                {account?.avatar_url && <AvatarImage alt={account.name} src={account.avatar_url} />}
                <AvatarFallback className="text-2xl md:text-3xl">{account?.initials || ""}</AvatarFallback>
              </Avatar>
            </div>

            <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-2xl font-bold tracking-tight">{account?.name || "Profile"}</h2>
                  <BadgeCheck className="h-5 w-5 text-sky-500" />
                </div>
                <div className="mt-1 flex items-center gap-1 text-muted-foreground">
                  <AtSign className="h-4 w-4" />
                  {account?.handle || "loading"}
                </div>
                <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">
                  Personal knowledge feed for digested notes, papers, concepts, and generated posts.
                </p>
              </div>
              <Button onClick={() => setActiveView("digest")}>
                <Upload className="h-4 w-4" />
                Digest Source
              </Button>
            </div>

            <div className="mt-6 flex flex-wrap gap-6 text-base">
              <div>
                <span className="font-bold">{posts.length}</span>{" "}
                <span className="text-muted-foreground">Posts</span>
              </div>
              <div>
                <span className="font-bold">{readyCount}</span>{" "}
                <span className="text-muted-foreground">Sources</span>
              </div>
              <div>
                <span className="font-bold">{conceptCount}</span>{" "}
                <span className="text-muted-foreground">Concepts</span>
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-5 px-5 pb-8 pt-5 xl:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="space-y-5">
            <Card className="rounded-lg shadow-none">
              <CardHeader>
                <CardTitle>Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  {sources.length} total saved sources
                </div>
                <div className="flex items-center gap-2">
                  <CalendarDays className="h-4 w-4" />
                  Building memory since 2026
                </div>
              </CardContent>
            </Card>
          </aside>

          <div className="min-w-0">
            <Tabs defaultValue="posts">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="posts">
                  <Grid2X2 className="mr-2 h-4 w-4" />
                  Posts
                </TabsTrigger>
                <TabsTrigger value="reposts">
                  <Repeat2 className="mr-2 h-4 w-4" />
                  Reposts
                </TabsTrigger>
                <TabsTrigger value="tags">
                  <Tag className="mr-2 h-4 w-4" />
                  Tags
                </TabsTrigger>
              </TabsList>

              <TabsContent className="mt-6" value="posts">
                {posts.length ? (
                  <div className="space-y-4">
                    {posts.map((post) => (
                      <Card className="rounded-lg shadow-none" key={post.id}>
                        <CardHeader className="flex-row gap-3 space-y-0">
                  <Avatar>
                    {account?.avatar_url && <AvatarImage alt={account.name} src={account.avatar_url} />}
                    <AvatarFallback>{account?.initials || ""}</AvatarFallback>
                  </Avatar>
                          <div>
                            <CardTitle className="text-base">{post.source_title}</CardTitle>
                            <CardDescription>
                              {account ? `${account.name} · ` : ""}
                              @{account?.handle || post.account_id} ·{" "}
                              {formatDate(post.created_at)} · AI-generated digest
                            </CardDescription>
                          </div>
                        </CardHeader>
                        <CardContent>
                          <p className="whitespace-pre-wrap leading-7">{post.body}</p>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <ProfileEmptyState setActiveView={setActiveView} />
                )}
              </TabsContent>

              <TabsContent className="mt-6" value="reposts">
                <ProfileEmptyState label="No reposts yet" />
              </TabsContent>

              <TabsContent className="mt-6" value="tags">
                <div className="grid gap-3 sm:grid-cols-2">
                  {["KnowledgeGraph", "PersonalAI", "DigestNotes", "ConceptMap"].map((tag) => (
                    <Card className="rounded-lg shadow-none" key={tag}>
                      <CardContent className="pt-6 text-lg font-bold">#{tag}</CardContent>
                    </Card>
                  ))}
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </section>
      </ScrollArea>
    </main>
  );
}

function ProfileEmptyState({
  label = "Nothing to see",
  setActiveView,
}: {
  label?: string;
  setActiveView?: (view: ActiveView) => void;
}) {
  return (
    <div className="grid min-h-[42vh] place-items-center text-center">
      <div>
        <Bug className="mx-auto mb-5 h-20 w-20 text-muted-foreground" />
        <h3 className="text-3xl font-bold tracking-tight">{label}</h3>
        <p className="mt-2 text-sm text-muted-foreground">Posts will appear here when you digest a source.</p>
        {setActiveView && (
          <Button className="mt-6" onClick={() => setActiveView("digest")}>
            <Upload className="h-4 w-4" />
            Digest Source
          </Button>
        )}
      </div>
    </div>
  );
}
