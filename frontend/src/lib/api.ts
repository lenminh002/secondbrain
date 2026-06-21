import type { AccountRecord, AgentTraceStep, ApiError, ChatHistoryMessage, ChatMessage, Citation, GraphContext, KnowledgeGraph, PostRecord, SourceDetail, SourceRecord, ToolCall } from "@/types";
import { auth } from "@/lib/firebase";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const ARCHIVE_POLL_INTERVAL_MS = 750;
const ARCHIVE_MAX_POLLS = 120;

async function getAuthHeaders(): Promise<Record<string, string>> {
  const user = auth.currentUser;
  if (user) {
    const token = await user.getIdToken();
    return { "Authorization": `Bearer ${token}` };
  }
  return {};
}

async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const authHeaders = await getAuthHeaders();
  const headers = {
    ...options.headers,
    ...authHeaders,
  };
  return fetch(url, { ...options, headers });
}

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
    authFetch(`${API_BASE_URL}/account`),
    authFetch(`${API_BASE_URL}/sources`),
    authFetch(`${API_BASE_URL}/posts`),
    authFetch(`${API_BASE_URL}/graph`),
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
  const response = await authFetch(`${API_BASE_URL}/sources/${sourceId}`);
  if (!response.ok) throw await responseError(response, "Source detail failed to load.");
  return (await response.json()) as SourceDetail;
}

export async function updateSourceContent(sourceId: string, content: string) {
  const response = await authFetch(`${API_BASE_URL}/sources/${sourceId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!response.ok) throw await responseError(response, "Memory update failed.");
  return (await response.json()) as SourceDetail;
}

export async function createSource(formData: FormData) {
  const response = await authFetch(`${API_BASE_URL}/sources`, {
    method: "POST",
    body: formData,
  });
  const payload = (await response.json()) as SourceRecord & ApiError;
  if (!response.ok) throw new Error(payload.detail || "Source ingestion failed.");
  return payload;
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function completedChatMessages(messages: ChatMessage[]) {
  return messages.filter((message) => !message.isStreaming && message.text.trim());
}

function formatArchiveDate(date: Date) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function chatArchiveTitle(date: Date) {
  return `Chat Archive - ${formatArchiveDate(date)}`;
}

function formatChatTranscript(messages: ChatMessage[], archivedAt: Date) {
  const completedMessages = completedChatMessages(messages);
  const lines = [
    "# Chat Archive",
    "",
    `Archived: ${archivedAt.toISOString()}`,
    `Messages: ${completedMessages.length}`,
    "",
    "## Transcript",
  ];

  completedMessages.forEach((message, index) => {
    const role = message.role === "user" ? "User" : "Assistant";
    lines.push("", `### ${role} ${index + 1}`, "", message.text.trim());

    if (message.role === "assistant" && message.citations?.length) {
      const citations = [
        ...new Set(
          message.citations
            .map((citation) => `${citation.source_title} / ${citation.section}`)
            .filter(Boolean),
        ),
      ];
      if (citations.length) {
        lines.push("", `Citations: ${citations.join("; ")}`);
      }
    }
  });

  return lines.join("\n");
}

export async function archiveChatSession(messages: ChatMessage[]) {
  const completedMessages = completedChatMessages(messages);
  if (!completedMessages.length) {
    throw new Error("No completed chat messages to archive.");
  }

  const archivedAt = new Date();
  const formData = new FormData();
  formData.append("type", "note");
  formData.append("title", chatArchiveTitle(archivedAt));
  formData.append("text", formatChatTranscript(completedMessages, archivedAt));

  const createdSource = await createSource(formData);
  let currentSource: SourceRecord | SourceDetail = createdSource;

  for (let attempt = 0; attempt < ARCHIVE_MAX_POLLS && currentSource.status === "processing"; attempt += 1) {
    await wait(ARCHIVE_POLL_INTERVAL_MS);
    currentSource = await fetchSourceDetail(createdSource.id);
  }

  if (currentSource.status === "processing") {
    throw new Error("Chat archive is still processing. Try again in a moment.");
  }
  if (currentSource.status === "failed") {
    throw new Error(currentSource.error || "Chat archive failed.");
  }

  return currentSource as SourceDetail;
}

export async function sendChatMessage(message: string, history: ChatHistoryMessage[] = []) {
  const response = await authFetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  const payload = (await response.json()) as {
    answer: string;
    citations?: Citation[];
    graph_context?: GraphContext[];
    tool_calls?: ToolCall[];
    agent_trace?: AgentTraceStep[];
  } & ApiError;
  if (!response.ok) throw new Error(payload.detail || "Chat failed.");
  return payload;
}

export interface StreamChatCallbacks {
  onText: (chunk: string) => void;
  onToolCall: (name: string) => void;
  onAgentStep?: (step: AgentTraceStep) => void;
  onDone: (
    citations: Citation[],
    graphContext: GraphContext[],
    toolCalls: ToolCall[],
    agentTrace: AgentTraceStep[],
  ) => void;
  onError?: (message: string) => void;
}

export async function streamChatMessage(
  message: string,
  callbacks: StreamChatCallbacks,
  history: ChatHistoryMessage[] = [],
): Promise<void> {
  const response = await authFetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
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
      } else if (type === "agent_step") {
        callbacks.onAgentStep?.(event as AgentTraceStep);
      } else if (type === "done") {
        callbacks.onDone(
          (event["citations"] as Citation[]) ?? [],
          (event["graph_context"] as GraphContext[]) ?? [],
          (event["tool_calls"] as ToolCall[]) ?? [],
          (event["agent_trace"] as AgentTraceStep[]) ?? [],
        );
        return;
      } else if (type === "error") {
        callbacks.onError?.(event["message"] as string);
        return;
      }
    }
  }
}
