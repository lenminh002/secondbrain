import { FormEvent, useEffect, useMemo, useState } from "react";
import { GitBranch } from "lucide-react";

import { MobileNav, SidebarNav, TopBar } from "@/components/AppNavigation";
import { ChatPanel } from "@/components/ChatPanel";
import { DigestSourcePage } from "@/components/DigestSourcePage";
import { HomeAside, HomeView } from "@/components/HomeView";
import { NotesView } from "@/components/NotesView";
import { ProfileView } from "@/components/ProfileView";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { createSource, fetchKnowledgeData, fetchSourceDetail, sendChatMessage } from "@/lib/api";
import { errorMessage } from "@/lib/format";
import type { AccountRecord, ActiveView, ChatMessage, KnowledgeGraph, NotesMode, PostRecord, SourceDetail, SourceRecord, SourceType } from "@/types";

const INGEST_POLL_INTERVAL_MS = 750;

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export default function App() {
  const [account, setAccount] = useState<AccountRecord | null>(null);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [posts, setPosts] = useState<PostRecord[]>([]);
  const [graph, setGraph] = useState<KnowledgeGraph>({ nodes: [], edges: [] });
  const [activeView, setActiveView] = useState<ActiveView>("home");
  const [notesMode, setNotesMode] = useState<NotesMode>("note");
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [selectedSourceDetail, setSelectedSourceDetail] = useState<SourceDetail | null>(null);
  const [activeType, setActiveType] = useState<SourceType>("note");
  const [title, setTitle] = useState("");
  const [noteText, setNoteText] = useState("");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [ingestProgress, setIngestProgress] = useState<SourceRecord | null>(null);
  const [notice, setNotice] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatLog, setChatLog] = useState<ChatMessage[]>([]);
  const [isChatting, setIsChatting] = useState(false);
  const [isSidebarMinimized, setIsSidebarMinimized] = useState(false);

  async function refresh() {
    const data = await fetchKnowledgeData();
    setAccount(data.account);
    setSources(data.sources);
    setPosts(data.posts);
    setGraph(data.graph);
    if (!selectedSourceId && data.sources.length) {
      setSelectedSourceId(data.sources[0].id);
    }
  }

  function refreshWithNotice() {
    refresh().catch((error: unknown) => setNotice(errorMessage(error)));
  }

  useEffect(() => {
    refreshWithNotice();
  }, []);

  useEffect(() => {
    if (!selectedSourceId) {
      setSelectedSourceDetail(null);
      return;
    }

    fetchSourceDetail(selectedSourceId)
      .then(setSelectedSourceDetail)
      .catch((error: unknown) => setNotice(errorMessage(error)));
  }, [selectedSourceId]);

  async function submitSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) return;
    if (activeType === "youtube") {
      setNotice("Video ingestion to be fixed.");
      return;
    }
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
        setYoutubeUrl("");
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

  async function submitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = chatInput.trim();
    if (!message) return;
    setChatInput("");
    setIsChatting(true);
    setChatLog((current) => [...current, { role: "user", text: message }]);
    try {
      const payload = await sendChatMessage(message);
      setChatLog((current) => [
        ...current,
        {
          role: "assistant",
          text: payload.answer,
          citations: payload.citations || [],
          graphContext: payload.graph_context || [],
          toolCalls: payload.tool_calls || [],
        },
      ]);
    } catch (error: unknown) {
      setChatLog((current) => [...current, { role: "assistant", text: errorMessage(error) }]);
    } finally {
      setIsChatting(false);
    }
  }

  const sourcesByType = useMemo(() => {
    return sources.reduce<Record<SourceType, SourceRecord[]>>(
      (groups, source) => {
        groups[source.type].push(source);
        return groups;
      },
      { note: [], pdf: [], youtube: [] },
    );
  }, [sources]);
  const readyCount = sources.filter((source) => source.status === "ready").length;
  const conceptCount = graph.nodes.filter((node) => node.type === "concept").length;
  const accountPosts = useMemo(() => {
    return account ? posts.filter((post) => post.account_id === account.id) : posts;
  }, [account, posts]);
  const chatPanel = (
    <ChatPanel chatInput={chatInput} chatLog={chatLog} isChatting={isChatting} setChatInput={setChatInput} submitChat={submitChat} />
  );

  return (
    <TooltipProvider>
      <div className="app-frame pb-20 lg:pb-0">
        <TopBar account={account} />
        <div
            className={activeView === "home" || activeView === "profile" ? "social-grid" : activeView === "digest" ? "digest-grid" : "notes-grid"}
            style={{ ["--sidebar-width" as string]: isSidebarMinimized ? "72px" : "260px" }}
          >
          <SidebarNav account={account} activeView={activeView} notesMode={notesMode} setActiveView={setActiveView} setNotesMode={setNotesMode} isMinimized={isSidebarMinimized} toggleMinimize={() => setIsSidebarMinimized((v) => !v)} />

          {activeView === "home" ? (
            <HomeView account={account} notice={notice} posts={accountPosts} refresh={refreshWithNotice} setActiveView={setActiveView} />
          ) : activeView === "profile" ? (
            <ProfileView account={account} conceptCount={conceptCount} posts={accountPosts} readyCount={readyCount} setActiveView={setActiveView} sources={sources} />
          ) : activeView === "digest" ? (
            <DigestSourcePage
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
              setYoutubeUrl={setYoutubeUrl}
              submitSource={submitSource}
              title={title}
              youtubeUrl={youtubeUrl}
            />
          ) : (
            <NotesView
              chatPanel={chatPanel}
              conceptCount={conceptCount}
              graph={graph}
              notesMode={notesMode}
              notice={notice}
              readyCount={readyCount}
              refreshGraph={refreshWithNotice}
              selectedSourceDetail={selectedSourceDetail}
              selectedSourceId={selectedSourceId}
              setNotesMode={setNotesMode}
              setSelectedSourceId={setSelectedSourceId}
              sourcesByType={sourcesByType}
            />
          )}

          {activeView === "home" || activeView === "profile" ? (
            <HomeAside account={account} setActiveView={setActiveView} setSelectedSourceId={setSelectedSourceId} sources={sources} />
          ) : activeView === "notes" ? (
            <aside className="sticky top-[74px] hidden h-[calc(100vh-74px)] lg:block">{chatPanel}</aside>
          ) : null}
        </div>
        <MobileNav activeView={activeView} setActiveView={setActiveView} />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button className="fixed bottom-20 right-4 z-40 rounded-full shadow-lg lg:hidden" onClick={() => { setActiveView("notes"); setNotesMode("graph"); }} size="icon">
              <GitBranch className="h-5 w-5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Graphify</TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  );
}
