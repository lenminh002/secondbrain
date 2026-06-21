import { useMemo, useState } from "react";
import { GitBranch } from "lucide-react";

import { MobileNav, SidebarNav, TopBar } from "@/components/navigation";
import { ChatPanel } from "@/components/ChatPanel";
import { IngestSourcePage } from "@/components/IngestSourcePage";
import { HomeAside, HomeView } from "@/components/HomeView";
import { NotesView } from "@/components/NotesView";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

import { useKnowledgeBase } from "@/hooks/useKnowledgeBase";
import { useSourceIngestion } from "@/hooks/useSourceIngestion";
import { useChatSession } from "@/hooks/useChatSession";
import type { ActiveView, NotesMode, SourceRecord, SourceType } from "@/types";

export default function App() {
  const [activeView, setActiveView] = useState<ActiveView>("home");
  const [notesMode, setNotesMode] = useState<NotesMode>("note");
  const [isSidebarMinimized, setIsSidebarMinimized] = useState(true);

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
    isSubmitting,
    ingestProgress,
    submitSource,
  } = useSourceIngestion({
    refresh,
    setSelectedSourceId,
    setActiveView,
    setNotesMode,
    setNotice,
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
      isMinimized={isChatMinimized}
      toggleMinimize={() => setIsChatMinimized((v) => !v)}
    />
  );

  return (
    <TooltipProvider>
      <div className="app-frame pb-20 lg:pb-0">
        <TopBar account={account} />
        <div
          className={activeView === "home" ? "social-grid" : activeView === "ingest" ? "ingest-grid" : activeView === "chat" ? "chat-grid" : "notes-grid"}
          style={{
            ["--sidebar-width" as string]: isSidebarMinimized ? "72px" : "260px",
            ["--chat-width" as string]: isChatMinimized ? "48px" : "360px"
          }}
        >
          <SidebarNav
            account={account}
            activeView={activeView}
            notesMode={notesMode}
            setActiveView={setActiveView}
            setNotesMode={setNotesMode}
            isMinimized={isSidebarMinimized}
            toggleMinimize={() => setIsSidebarMinimized((v) => !v)}
          />

          {activeView === "home" ? (
            <HomeView
              account={account}
              notice={notice}
              posts={accountPosts}
              refresh={refreshWithNotice}
              setActiveView={setActiveView}
            />
          ) : activeView === "ingest" ? (
            <IngestSourcePage
              activeType={activeType}
              ingestProgress={ingestProgress}
              isSubmitting={isSubmitting}
              noteText={noteText}
              notice={notice}
              pdfFile={pdfFile}
              setActiveType={setActiveType}
              setNoteText={setNoteText}
              setPdfFile={setPdfFile}
              setTitle={setTitle}
              submitSource={submitSource}
              title={title}
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
            <aside className="sticky top-[74px] hidden h-[calc(100vh-74px)] lg:block">
              {chatPanel}
            </aside>
          ) : null}
        </div>
        <MobileNav activeView={activeView} setActiveView={setActiveView} />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              className="fixed bottom-20 right-4 z-40 rounded-full shadow-lg lg:hidden"
              onClick={() => {
                setActiveView("notes");
                setNotesMode("graph");
              }}
              size="icon"
            >
              <GitBranch className="h-5 w-5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Graphify</TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  );
}
