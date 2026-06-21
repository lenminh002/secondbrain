import { useEffect, useState } from "react";
import { fetchKnowledgeData, fetchSourceDetail } from "@/lib/api";
import { errorMessage } from "@/lib/format";
import type { AccountRecord, KnowledgeGraph, PostRecord, SourceDetail, SourceRecord } from "@/types";

export function useKnowledgeBase() {
  const [account, setAccount] = useState<AccountRecord | null>(null);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [posts, setPosts] = useState<PostRecord[]>([]);
  const [graph, setGraph] = useState<KnowledgeGraph>({ nodes: [], edges: [] });
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [selectedSourceDetail, setSelectedSourceDetail] = useState<SourceDetail | null>(null);
  const [notice, setNotice] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  async function refresh() {
    setIsLoading(true);
    try {
      const data = await fetchKnowledgeData();
      setAccount(data.account);
      setSources(data.sources);
      setPosts(data.posts);
      setGraph(data.graph);
      if (!selectedSourceId && data.sources.length) {
        setSelectedSourceId(data.sources[0].id);
      }
    } finally {
      setIsLoading(false);
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

  return {
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
  };
}
