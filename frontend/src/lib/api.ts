import type { AccountRecord, ApiError, Citation, KnowledgeGraph, PostRecord, SourceDetail, SourceRecord } from "@/types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function fetchKnowledgeData() {
  const [accountResponse, sourceResponse, postResponse, graphResponse] = await Promise.all([
    fetch(`${API_BASE_URL}/account`),
    fetch(`${API_BASE_URL}/sources`),
    fetch(`${API_BASE_URL}/posts`),
    fetch(`${API_BASE_URL}/graph`),
  ]);

  if (!accountResponse.ok || !sourceResponse.ok || !postResponse.ok || !graphResponse.ok) {
    throw new Error("Knowledge API returned an error.");
  }

  return {
    account: (await accountResponse.json()) as AccountRecord,
    sources: (await sourceResponse.json()) as SourceRecord[],
    posts: (await postResponse.json()) as PostRecord[],
    graph: (await graphResponse.json()) as KnowledgeGraph,
  };
}

export async function fetchSourceDetail(sourceId: string) {
  const response = await fetch(`${API_BASE_URL}/sources/${sourceId}`);
  if (!response.ok) throw new Error("Source detail failed to load.");
  return (await response.json()) as SourceDetail;
}

export async function createSource(formData: FormData) {
  const response = await fetch(`${API_BASE_URL}/sources`, { method: "POST", body: formData });
  const payload = (await response.json()) as SourceRecord & ApiError;
  if (!response.ok) throw new Error(payload.detail || "Source ingestion failed.");
  return payload;
}

export async function sendChatMessage(message: string) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  const payload = (await response.json()) as { answer: string; citations?: Citation[] } & ApiError;
  if (!response.ok) throw new Error(payload.detail || "Chat failed.");
  return payload;
}
