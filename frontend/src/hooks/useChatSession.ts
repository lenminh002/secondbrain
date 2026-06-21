import { FormEvent, useState } from "react";
import { streamChatMessage } from "@/lib/api";
import { errorMessage } from "@/lib/format";
import type { ChatMessage } from "@/types";

export function useChatSession() {
  const [chatInput, setChatInput] = useState("");
  const [chatLog, setChatLog] = useState<ChatMessage[]>([]);
  const [isChatting, setIsChatting] = useState(false);
  const [isChatMinimized, setIsChatMinimized] = useState(true);

  async function submitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = chatInput.trim();
    if (!message || isChatting) return;
    setChatInput("");
    setIsChatting(true);

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
      });
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
    isChatting,
    isChatMinimized,
    setIsChatMinimized,
    submitChat,
  };
}
