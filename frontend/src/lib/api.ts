import type { AccountRecord, ApiError, Citation, GraphContext, KnowledgeGraph, PostRecord, SourceDetail, SourceRecord, ToolCall } from "@/types";

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
  } & ApiError;
  if (!response.ok) throw new Error(payload.detail || "Chat failed.");
  return payload;
}

export interface StreamChatCallbacks {
  onText: (chunk: string) => void;
  onToolCall: (name: string) => void;
  onDone: (citations: Citation[], graphContext: GraphContext[], toolCalls: ToolCall[]) => void;
  onError?: (message: string) => void;
}

export async function streamChatMessage(
  message: string,
  callbacks: StreamChatCallbacks,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!response.ok || !response.body) {
    const payload = (await response.json().catch(() => ({}))) as ApiError;
    throw new Error(payload.detail || "Streaming chat failed.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6).trim();
      if (!raw) continue;
      let event: Record<string, unknown>;
      try {
        event = JSON.parse(raw) as Record<string, unknown>;
      } catch {
        continue;
      }

      const type = event["type"] as string;
      if (type === "text") {
        callbacks.onText(event["text"] as string);
      } else if (type === "tool_call") {
        callbacks.onToolCall(event["name"] as string);
      } else if (type === "done") {
        callbacks.onDone(
          (event["citations"] as Citation[]) ?? [],
          (event["graph_context"] as GraphContext[]) ?? [],
          (event["tool_calls"] as ToolCall[]) ?? [],
        );
        return;
      } else if (type === "error") {
        callbacks.onError?.(event["message"] as string);
        return;
      }
    }
  }
}
