import { useMemo, useState } from "react";
import { Bot, FileText } from "lucide-react";

import { MobileNav, SidebarNav, TopBar } from "@/components/navigation";
import { AddSelectionToChat } from "@/components/AddSelectionToChat";
import { ChatPanel } from "@/components/ChatPanel";
import { IngestSourceDrawer } from "@/components/IngestSourceDrawer";
import { HomeAside, HomeView } from "@/components/HomeView";
import { NotesView } from "@/components/NotesView";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { StatusBadge } from "@/components/StatusBadge";
import { cn } from "@/lib/utils";
import { formatDate } from "@/lib/format";
import type { ActiveView, NotesMode, SourceRecord, SourceType } from "@/types";

import { useKnowledgeBase } from "@/hooks/useKnowledgeBase";
import { useSourceIngestion } from "@/hooks/useSourceIngestion";
import { useChatSession } from "@/hooks/useChatSession";
import { useAuth } from "@/hooks/useAuth";
import { LoginView } from "@/components/LoginView";

export default function App() {
  const { user, loading, loginWithGoogle } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-[#0d0f14]">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-indigo-500 border-t-transparent"></div>
      </div>
    );
  }

  if (!user) {
    return <LoginView onLogin={loginWithGoogle} />;
  }

  return <AuthenticatedApp />;
}

function AuthenticatedApp() {
  const [activeView, setActiveView] = useState<ActiveView>("home");
  const [notesMode, setNotesMode] = useState<NotesMode>("note");
  const [isIngestOpen, setIsIngestOpen] = useState(false);
  const isSidebarMinimized = false;
  const [memoriesSidebarTab, setMemoriesSidebarTab] = useState<"chat" | "vault">("vault");

  const {
    account,
    sources,
    posts,
    graph,
    selectedSourceId,
    setSelectedSourceId,
    selectedSourceDetail,
    setSelectedSourceDetail,
    notice,
    setNotice,
    refresh,
    refreshWithNotice,
    isLoading,
  } = useKnowledgeBase();

  const {
    activeType,
    setActiveType,
    title,
    setTitle,
    noteText,
    setNoteText,
    pdfFile,
    setPdfFile,
    thumbnailUrl,
    setThumbnailUrl,
    isSubmitting,
    ingestProgress,
    submitSource,
  } = useSourceIngestion({
    refresh,
    setSelectedSourceId,
    setActiveView,
    setNotesMode,
    setNotice,
    onSuccess: () => setIsIngestOpen(false),
  });

  const {
    chatInput,
    setChatInput,
    chatLog,
    isChatting,
    isChatMinimized,
    setIsChatMinimized,
    submitChat,
    clearChatHistory,
    archiveAndClearChatHistory,
    isArchivingChat,
    chatArchiveError,
  } = useChatSession({ onArchiveComplete: refresh });

  const sourcesByType = useMemo(() => {
    return sources.reduce<Record<SourceType, SourceRecord[]>>(
      (groups, source) => {
        groups[source.type].push(source);
        return groups;
      },
      { note: [], pdf: [] },
    );
  }, [sources]);

  const readyCount = sources.filter((source) => source.status === "ready").length;
  const conceptCount = graph.nodes.filter((node) => node.type === "concept").length;
  const accountPosts = useMemo(() => {
    return account ? posts.filter((post) => post.account_id === account.id) : posts;
  }, [account, posts]);

  const chatPanel = (
    <ChatPanel
      chatInput={chatInput}
      chatLog={chatLog}
      isChatting={isChatting}
      setChatInput={setChatInput}
      submitChat={submitChat}
      clearChatHistory={clearChatHistory}
      archiveChatHistory={archiveAndClearChatHistory}
      isArchivingChat={isArchivingChat}
      chatArchiveError={chatArchiveError}
      isMinimized={activeView === "notes" ? false : isChatMinimized}
      toggleMinimize={activeView === "notes" ? undefined : () => setIsChatMinimized((v) => !v)}
    />
  );

  function addSelectionToChat(quotedText: string) {
    setChatInput((current) => current.trim() ? `${current.trim()}\n\n${quotedText}` : quotedText);
    setIsChatMinimized(false);
    if (activeView === "notes") {
      setMemoriesSidebarTab("chat");
    } else {
      setActiveView("chat");
    }
  }

  return (
    <TooltipProvider>
      <div className="app-frame pb-20 lg:pb-0">
        <AddSelectionToChat onAdd={addSelectionToChat} />
        <TopBar account={account} />
        <div
          className={activeView === "home" ? "social-grid" : activeView === "ingest" ? "ingest-grid" : activeView === "chat" ? "chat-grid" : "notes-grid"}
          style={{
            ["--sidebar-width" as string]: isSidebarMinimized ? "72px" : "260px",
            ["--chat-width" as string]: (activeView === "notes" ? false : isChatMinimized) ? "48px" : "360px"
          }}
        >
          <SidebarNav
            account={account}
            activeView={activeView}
            notesMode={notesMode}
            setActiveView={setActiveView}
            setNotesMode={setNotesMode}
            isMinimized={isSidebarMinimized}
            onIngestClick={() => setIsIngestOpen(true)}
          />

          {activeView === "home" ? (
            <HomeView
              account={account}
              notice={notice}
              posts={accountPosts}
              refresh={refreshWithNotice}
              setActiveView={setActiveView}
              onIngestClick={() => setIsIngestOpen(true)}
              isLoading={isLoading}
            />
          ) : activeView === "chat" ? (
            <div className="h-[calc(100vh-74px)]">
              <ChatPanel
                chatInput={chatInput}
                chatLog={chatLog}
                isChatting={isChatting}
                setChatInput={setChatInput}
                submitChat={submitChat}
                clearChatHistory={clearChatHistory}
                archiveChatHistory={archiveAndClearChatHistory}
                isArchivingChat={isArchivingChat}
                chatArchiveError={chatArchiveError}
              />
            </div>
          ) : (
            <NotesView
              chatPanel={chatPanel}
              conceptCount={conceptCount}
              graph={graph}
              notesMode={notesMode}
              notice={notice}
              readyCount={readyCount}
              refreshKnowledge={refresh}
              selectedSourceDetail={selectedSourceDetail}
              selectedSourceId={selectedSourceId}
              setNotice={setNotice}
              setNotesMode={setNotesMode}
              setSelectedSourceId={setSelectedSourceId}
              setSelectedSourceDetail={setSelectedSourceDetail}
              sourcesByType={sourcesByType}
              sidebarTab={memoriesSidebarTab}
              setSidebarTab={setMemoriesSidebarTab}
            />
          )}

          {activeView === "home" ? (
            <HomeAside
              account={account}
              setActiveView={setActiveView}
              setSelectedSourceId={setSelectedSourceId}
              sources={sources}
            />
          ) : activeView === "notes" ? (
            <aside className="sticky top-[74px] hidden h-[calc(100vh-74px)] lg:flex lg:flex-col border-l bg-background w-[var(--chat-width,360px)]">
              <div className="flex h-14 shrink-0 items-center justify-between gap-3 border-b px-4">
                <div className="flex min-w-0 items-center gap-2 text-lg font-bold">
                  {memoriesSidebarTab === "chat" ? <Bot className="h-5 w-5 shrink-0" /> : <FileText className="h-5 w-5 shrink-0" />}
                  <span className="truncate">{memoriesSidebarTab === "chat" ? "Librarian" : "Vault"}</span>
                </div>
                <div className="flex shrink-0 rounded-lg bg-muted p-1">
                  <Button
                    className="h-8 px-3 text-xs"
                    onClick={() => setMemoriesSidebarTab("vault")}
                    size="sm"
                    type="button"
                    variant={memoriesSidebarTab === "vault" ? "secondary" : "ghost"}
                  >
                    Vault
                  </Button>
                  <Button
                    className="h-8 px-3 text-xs"
                    onClick={() => setMemoriesSidebarTab("chat")}
                    size="sm"
                    type="button"
                    variant={memoriesSidebarTab === "chat" ? "secondary" : "ghost"}
                  >
                    Librarian
                  </Button>
                </div>
              </div>
              <div className="min-h-0 flex-1">
                {memoriesSidebarTab === "chat" ? (
                  chatPanel
                ) : (
                  <ScrollArea className="h-full">
                  <div className="space-y-5 p-4">
                    <div>
                      <div className="space-y-4">
                        {(["note", "pdf"] as const).map((type) => (
                          <div key={type}>
                            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{type}</div>
                            <div className="space-y-1">
                              {sourcesByType[type].length ? (
                                sourcesByType[type].map((source) => (
                                  <button
                                    className={cn(
                                      "w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-muted transition-colors duration-150",
                                      selectedSourceId === source.id && "bg-muted font-medium",
                                    )}
                                    key={source.id}
                                    onClick={() => { setSelectedSourceId(source.id); setNotesMode("note"); }}
                                    type="button"
                                  >
                                    <span className="flex w-full items-start justify-between gap-2 min-w-0">
                                      <span className="min-w-0">
                                        <span className="block truncate font-medium">{source.title}</span>
                                        <span className="text-xs text-muted-foreground">{formatDate(source.created_at)}</span>
                                      </span>
                                      {source.status !== "ready" && <StatusBadge status={source.status} />}
                                    </span>
                                  </button>
                                ))
                              ) : (
                                <div className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground">No {type} sources</div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                  </ScrollArea>
                )}
              </div>
            </aside>
          ) : null}
        </div>
        <MobileNav
          activeView={activeView}
          setActiveView={setActiveView}
          onIngestClick={() => setIsIngestOpen(true)}
          notesMode={notesMode}
          setNotesMode={setNotesMode}
        />
        <IngestSourceDrawer
          isOpen={isIngestOpen}
          onOpenChange={setIsIngestOpen}
          activeType={activeType}
          ingestProgress={ingestProgress}
          isSubmitting={isSubmitting}
          noteText={noteText}
          notice={notice}
          pdfFile={pdfFile}
          thumbnailUrl={thumbnailUrl}
          setThumbnailUrl={setThumbnailUrl}
          setActiveType={setActiveType}
          setNoteText={setNoteText}
          setPdfFile={setPdfFile}
          setTitle={setTitle}
          submitSource={submitSource}
          title={title}
        />
      </div>
    </TooltipProvider>
  );
}
