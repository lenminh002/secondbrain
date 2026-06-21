import type { AccountRecord, ApiError, Citation, GraphContext, KnowledgeGraph, PendingAction, PostRecord, SourceDetail, SourceRecord, ToolCall } from "@/types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function responseError(response: Response, fallback: string) {
  try {
    const payload = (await response.json()) as ApiError;
    return new Error(payload.detail || fallback);
  } catch {
    return new Error(fallback);
  }
}

export async function fetchKnowledgeData() {
  const [accountResponse, sourceResponse, postResponse, graphResponse] = await Promise.all([
    fetch(`${API_BASE_URL}/account`),
    fetch(`${API_BASE_URL}/sources`),
    fetch(`${API_BASE_URL}/posts`),
    fetch(`${API_BASE_URL}/graph`),
  ]);

  const failedResponse = [accountResponse, sourceResponse, postResponse, graphResponse].find(
    (response) => !response.ok,
  );
  if (failedResponse) {
    throw await responseError(failedResponse, "Knowledge API returned an error.");
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
  if (!response.ok) throw await responseError(response, "Source detail failed to load.");
  return (await response.json()) as SourceDetail;
}

export async function createSource(formData: FormData) {
  const response = await fetch(`${API_BASE_URL}/sources`, {
    method: "POST",
    body: formData,
  });
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
  const payload = (await response.json()) as {
    answer: string;
    citations?: Citation[];
    graph_context?: GraphContext[];
    tool_calls?: ToolCall[];
    pending_action?: PendingAction | null;
  } & ApiError;
  if (!response.ok) throw new Error(payload.detail || "Chat failed.");
  return payload;
}

export async function deleteSource(sourceId: string) {
  const response = await fetch(`${API_BASE_URL}/sources/${sourceId}`, {
    method: "DELETE",
  });
  if (!response.ok) throw await responseError(response, "Failed to delete source.");
  return (await response.json()) as { status: string; source_id: string };
}
