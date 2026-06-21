import { FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Trash2, Bot, GitBranch, Loader2, MessageCircle, ChevronRight, ChevronLeft } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types";

export function ChatPanel({
  chatInput,
  chatLog,
  isChatting,
  setChatInput,
  submitChat,
  clearChatHistory,
  archiveChatHistory,
  isArchivingChat = false,
  chatArchiveError = "",
  isMinimized,
  toggleMinimize,
}: {
  chatInput: string;
  chatLog: ChatMessage[];
  isChatting: boolean;
  setChatInput: (value: string) => void;
  submitChat: (event: FormEvent<HTMLFormElement>) => void;
  clearChatHistory?: () => void;
  archiveChatHistory?: () => void;
  isArchivingChat?: boolean;
  chatArchiveError?: string;
  isMinimized?: boolean;
  toggleMinimize?: () => void;
}) {
  const hasCompletedMessages = chatLog.some((message) => !message.isStreaming && message.text.trim());

  if (isMinimized) {
    return (
      <Card className="flex h-full min-h-0 flex-col rounded-none border-0 shadow-none lg:rounded-none bg-muted/20 items-center py-4">
        {toggleMinimize && (
          <Button variant="ghost" size="icon" onClick={toggleMinimize} className="mb-4">
            <ChevronLeft className="h-5 w-5" />
          </Button>
        )}
        <Bot className="h-5 w-5 text-muted-foreground" />
      </Card>
    );
  }

  return (
    <Card className="flex h-full min-h-0 flex-col rounded-none border-0 shadow-none lg:rounded-none relative">
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-3 p-4">
          {chatLog.length ? (
            chatLog.map((message, index) => {
              const graphConcepts = [
                ...new Set((message.graphContext || []).map((item) => item.concept_label).filter(Boolean)),
              ];
              return (
                <div
                  className={cn(
                    "rounded-2xl border p-3 text-sm leading-6",
                    message.role === "user" ? "ml-8 bg-primary text-primary-foreground" : "mr-8 bg-muted/45",
                  )}
                  key={`${message.role}-${index}`}
                >
                  {!!message.toolCalls?.length && (
                    <div className="mb-2 flex flex-wrap gap-1">
                      {message.toolCalls.map((toolCall, toolIndex) => (
                        <Badge key={`${toolCall.name}-${toolIndex}`} variant="outline">
                          Using tool {toolCall.name}
                        </Badge>
                      ))}
                    </div>
                  )}
                  {!!message.agentTrace?.length && (
                    <div className="mb-3 space-y-1 rounded-lg border bg-background/55 p-2 text-xs">
                      <div className="font-medium text-muted-foreground">Agent system</div>
                      {message.agentTrace.slice(0, 6).map((step, stepIndex) => (
                        <div className="flex items-start gap-2" key={`${step.stage}-${stepIndex}`}>
                          <Badge variant={step.status === "warning" ? "outline" : "secondary"} className="shrink-0">
                            {step.stage}
                          </Badge>
                          <div className="min-w-0">
                            <div className="font-medium leading-5">{step.title}</div>
                            {step.detail && (
                              <div className="line-clamp-2 text-muted-foreground">{step.detail}</div>
                            )}
                          </div>
                        </div>
                      ))}
                      {message.agentTrace.length > 6 && (
                        <div className="text-muted-foreground">+{message.agentTrace.length - 6} more steps</div>
                      )}
                    </div>
                  )}
                  {!!graphConcepts.length && (
                    <div className="mb-2 flex flex-wrap gap-1">
                      <Badge className="gap-1" variant="outline">
                        <GitBranch className="h-3 w-3" />
                        Expanded via graph concepts
                      </Badge>
                      {graphConcepts.slice(0, 3).map((concept) => (
                        <Badge key={concept} variant="secondary">
                          {concept}
                        </Badge>
                      ))}
                    </div>
                  )}
                  {message.role === "assistant" ? (
                    <div className="prose prose-sm dark:prose-invert max-w-none [&_*]:text-inherit text-current">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {message.text}
                      </ReactMarkdown>
                      {message.isStreaming && (
                        <span className="inline-block w-[3px] h-[1em] bg-current align-middle ml-0.5 animate-pulse" />
                      )}
                    </div>
                  ) : (
                    <p>{message.text}</p>
                  )}
                  {!!message.citations?.length && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {message.citations.map((citation, citationIndex) => {
                        const isGraphNeighbor = citation.retrieval === "graph_neighbor";
                        return (
                          <Badge
                            key={`${citation.source_id}-${citation.section}-${citationIndex}`}
                            variant={isGraphNeighbor ? "outline" : "secondary"}
                          >
                            {isGraphNeighbor && citation.matched_concept_label
                              ? `Graph: ${citation.matched_concept_label} - ${citation.source_title}`
                              : citation.source_title}{" "}
                            / {citation.section}
                          </Badge>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
              Hi. I'm the Librarian, Second Brain's AI Agent. Tell me to do something.
            </div>
          )}
        </div>
      </ScrollArea>
      <form className="flex gap-2 border-t p-4" onSubmit={submitChat}>
        <Input
          disabled={isArchivingChat}
          value={chatInput}
          onChange={(event) => setChatInput(event.target.value)}
          placeholder="Ask your KB..."
        />
        <Button disabled={isChatting || isArchivingChat} type="submit">
          {isChatting ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageCircle className="h-4 w-4" />}
        </Button>
      </form>
    </Card>
  );
}
