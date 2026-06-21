import type { AccountRecord, ApiError, Citation, KnowledgeGraph, PostRecord, SourceDetail, SourceRecord } from "@/types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

export async function fetchKnowledgeData(token: string) {
  const [accountResponse, sourceResponse, postResponse, graphResponse] = await Promise.all([
    fetch(`${API_BASE_URL}/account`, { headers: authHeaders(token) }),
    fetch(`${API_BASE_URL}/sources`, { headers: authHeaders(token) }),
    fetch(`${API_BASE_URL}/posts`, { headers: authHeaders(token) }),
    fetch(`${API_BASE_URL}/graph`, { headers: authHeaders(token) }),
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

export async function fetchSourceDetail(token: string, sourceId: string) {
  const response = await fetch(`${API_BASE_URL}/sources/${sourceId}`, { headers: authHeaders(token) });
  if (!response.ok) throw new Error("Source detail failed to load.");
  return (await response.json()) as SourceDetail;
}

export async function createSource(token: string, formData: FormData) {
  const response = await fetch(`${API_BASE_URL}/sources`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });
  const payload = (await response.json()) as SourceRecord & ApiError;
  if (!response.ok) throw new Error(payload.detail || "Source ingestion failed.");
  return payload;
}

export async function sendChatMessage(token: string, message: string) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ message }),
  });
  const payload = (await response.json()) as { answer: string; citations?: Citation[] } & ApiError;
  if (!response.ok) throw new Error(payload.detail || "Chat failed.");
  return payload;
}
