import { FormEvent, useEffect, useState } from "react";
import { archiveChatSession, streamChatMessage } from "@/lib/api";
import { errorMessage } from "@/lib/format";
import type { ChatHistoryMessage, ChatMessage, SourceDetail } from "@/types";

const CHAT_HISTORY_STORAGE_KEY = "skywatch.chat.history.v1";
const MAX_CLIENT_HISTORY_MESSAGES = 20;

function normalizeChatMessages(value: unknown): ChatMessage[] {
  if (!Array.isArray(value)) return [];
  return value.reduce<ChatMessage[]>((messages, item) => {
    if (!item || typeof item !== "object") return messages;
    const message = item as Partial<ChatMessage>;
    if (message.role !== "user" && message.role !== "assistant") return messages;
    const text = typeof message.text === "string" ? message.text : "";
    if (!text.trim()) return messages;
    messages.push({
      ...message,
      role: message.role,
      text,
      isStreaming: false,
    });
    return messages;
  }, []);
}

function loadStoredChatLog(): ChatMessage[] {
  if (typeof window === "undefined") return [];
  try {
    const stored = window.localStorage.getItem(CHAT_HISTORY_STORAGE_KEY);
    if (!stored) return [];
    return normalizeChatMessages(JSON.parse(stored));
  } catch {
    return [];
  }
}

function messagesForStorage(messages: ChatMessage[]): ChatMessage[] {
  return messages
    .filter((message) => !message.isStreaming && message.text.trim())
    .map((message) => {
      const storedMessage = { ...message };
      delete storedMessage.isStreaming;
      return storedMessage;
    });
}

function messagesForRequestHistory(messages: ChatMessage[]): ChatHistoryMessage[] {
  return messagesForStorage(messages)
    .slice(-MAX_CLIENT_HISTORY_MESSAGES)
    .map(({ role, text }) => ({ role, text }));
}

export function useChatSession({
  onArchiveComplete,
}: {
  onArchiveComplete?: (source: SourceDetail) => Promise<void> | void;
} = {}) {
  const [chatInput, setChatInput] = useState("");
  const [chatLog, setChatLog] = useState<ChatMessage[]>(loadStoredChatLog);
  const [isChatting, setIsChatting] = useState(false);
  const [isArchivingChat, setIsArchivingChat] = useState(false);
  const [chatArchiveError, setChatArchiveError] = useState("");
  const [isChatMinimized, setIsChatMinimized] = useState(true);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedMessages = messagesForStorage(chatLog);
    if (!storedMessages.length) {
      window.localStorage.removeItem(CHAT_HISTORY_STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(CHAT_HISTORY_STORAGE_KEY, JSON.stringify(storedMessages));
  }, [chatLog]);

  function clearChatHistory() {
    setChatInput("");
    setChatLog([]);
    setChatArchiveError("");
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(CHAT_HISTORY_STORAGE_KEY);
    }
  }

  async function archiveAndClearChatHistory() {
    if (isChatting || isArchivingChat) return;
    const messagesToArchive = messagesForStorage(chatLog);
    if (!messagesToArchive.length) return;

    setIsArchivingChat(true);
    setChatArchiveError("");
    try {
      const archivedSource = await archiveChatSession(messagesToArchive);
      await onArchiveComplete?.(archivedSource);
      clearChatHistory();
    } catch (error: unknown) {
      setChatArchiveError(errorMessage(error));
    } finally {
      setIsArchivingChat(false);
    }
  }

  async function submitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = chatInput.trim();
    if (!message || isChatting || isArchivingChat) return;
    const history = messagesForRequestHistory(chatLog);
    setChatInput("");
    setIsChatting(true);
    setChatArchiveError("");

    // Add user message + placeholder assistant message immediately.
    setChatLog((current) => [
      ...current,
      { role: "user", text: message },
      { role: "assistant", text: "", isStreaming: true },
    ]);

    try {
      await streamChatMessage(message, {
        onText(chunk) {
          setChatLog((current) => {
            const updated = [...current];
            const last = updated[updated.length - 1];
            if (last?.role === "assistant") {
              updated[updated.length - 1] = { ...last, text: last.text + chunk };
            }
            return updated;
          });
        },
        onToolCall(name) {
          setChatLog((current) => {
            const updated = [...current];
            const last = updated[updated.length - 1];
            if (last?.role === "assistant") {
              updated[updated.length - 1] = {
                ...last,
                toolCalls: [...(last.toolCalls ?? []), { name }],
              };
            }
            return updated;
          });
        },
        onAgentStep(step) {
          setChatLog((current) => {
            const updated = [...current];
            const last = updated[updated.length - 1];
            if (last?.role === "assistant") {
              updated[updated.length - 1] = {
                ...last,
                agentTrace: [...(last.agentTrace ?? []), step],
              };
            }
            return updated;
          });
        },
        onDone(citations, graphContext, toolCalls, agentTrace) {
          setChatLog((current) => {
            const updated = [...current];
            const last = updated[updated.length - 1];
            if (last?.role === "assistant") {
              updated[updated.length - 1] = {
                ...last,
                isStreaming: false,
                citations,
                graphContext,
                toolCalls,
                agentTrace,
              };
            }
            return updated;
          });
        },
        onError(msg) {
          setChatLog((current) => {
            const updated = [...current];
            const last = updated[updated.length - 1];
            if (last?.role === "assistant") {
              updated[updated.length - 1] = { ...last, text: msg, isStreaming: false };
            }
            return updated;
          });
        },
      }, history);
    } catch (error: unknown) {
      setChatLog((current) => {
        const updated = [...current];
        const last = updated[updated.length - 1];
        if (last?.role === "assistant") {
          updated[updated.length - 1] = { ...last, text: errorMessage(error), isStreaming: false };
        }
        return updated;
      });
    } finally {
      setIsChatting(false);
    }
  }

  return {
    chatInput,
    setChatInput,
    chatLog,
    setChatLog,
    clearChatHistory,
    archiveAndClearChatHistory,
    isChatting,
    isArchivingChat,
    chatArchiveError,
    isChatMinimized,
    setIsChatMinimized,
    submitChat,
  };
}
