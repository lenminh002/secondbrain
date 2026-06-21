import { FormEvent } from "react";
import { Bot, Check, GitBranch, Loader2, MessageCircle, Trash2, X } from "lucide-react";

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
}: {
  chatInput: string;
  chatLog: ChatMessage[];
  isChatting: boolean;
  setChatInput: (value: string) => void;
  submitChat: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <Card className="flex h-full min-h-0 flex-col rounded-none border-0 border-l shadow-none">
      <CardHeader className="border-b">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          <CardTitle>AI Sidebar</CardTitle>
        </div>
        <CardDescription>Ask across notes, graph nodes, and generated posts.</CardDescription>
      </CardHeader>
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
                    "rounded-lg border p-3 text-sm leading-6",
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
                  <p>{message.text}</p>
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
            <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
              Ask what your saved knowledge says about a topic.
            </div>
          )}
        </div>
      </ScrollArea>
      <form className="flex gap-2 border-t p-4" onSubmit={submitChat}>
        <Input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="Ask your KB..." />
        <Button disabled={isChatting} type="submit">
          {isChatting ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageCircle className="h-4 w-4" />}
        </Button>
      </form>
    </Card>
  );
}

function ChatBubble({ message }: { message: ChatMessage }) {
  const graphConcepts = [
    ...new Set((message.graphContext || []).map((item) => item.concept_label).filter(Boolean)),
  ];
  return (
    <div
      className={cn(
        "rounded-lg p-3 text-sm leading-6",
        message.role === "user" ? "ml-8 bg-primary text-primary-foreground" : "mr-8 bg-muted/45",
      )}
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
      <p className="whitespace-pre-wrap">{message.text}</p>
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
}

export function ChatView({
  chatInput,
  chatLog,
  isChatting,
  setChatInput,
  submitChat,
  onConfirmDelete,
  onCancelDelete,
}: {
  chatInput: string;
  chatLog: ChatMessage[];
  isChatting: boolean;
  setChatInput: (value: string) => void;
  submitChat: (event: FormEvent<HTMLFormElement>) => void;
  onConfirmDelete: (index: number, sourceId: string) => void;
  onCancelDelete: (index: number) => void;
}) {
  return (
    <main className="flex h-[calc(100vh-74px)] min-h-0 flex-col bg-background">
      <div className="flex h-14 shrink-0 items-center gap-2 px-5">
        <Bot className="h-5 w-5" />
        <div>
          <h1 className="font-bold leading-none">Chat</h1>
          <p className="text-xs text-muted-foreground">Ask across your knowledge, create notes, and delete sources.</p>
        </div>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto max-w-3xl space-y-3 p-4 sm:p-5">
          {chatLog.length ? (
            chatLog.map((message, index) => (
              <div key={`${message.role}-${index}`}>
                <ChatBubble message={message} />
                {message.pendingAction?.type === "delete_source" && !message.resolved && (
                  <div className="mr-8 mt-2 rounded-lg bg-destructive/5 p-3 text-sm">
                    <div className="mb-1 flex items-center gap-2 font-medium text-destructive">
                      <Trash2 className="h-4 w-4" />
                      Delete “{message.pendingAction.title || message.pendingAction.source_id}”?
                    </div>
                    <p className="mb-3 text-muted-foreground">
                      This permanently removes the source and its notes, posts, and graph entries.
                    </p>
                    <div className="flex gap-2">
                      <Button
                        onClick={() => onConfirmDelete(index, message.pendingAction!.source_id)}
                        size="sm"
                        variant="destructive"
                      >
                        <Check className="h-4 w-4" />
                        Confirm delete
                      </Button>
                      <Button onClick={() => onCancelDelete(index)} size="sm" variant="outline">
                        <X className="h-4 w-4" />
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
                {message.pendingAction?.type === "delete_source" && message.resolved && (
                  <div className="mr-8 mt-2 text-xs text-muted-foreground">Action resolved.</div>
                )}
              </div>
            ))
          ) : (
            <div className="rounded-lg bg-muted/45 p-4 text-sm text-muted-foreground">
              Try “what do my notes say about transformers”, “create a note titled Ideas with …”, or “delete the note about X”.
            </div>
          )}
        </div>
      </ScrollArea>
      <form className="mx-auto flex w-full max-w-3xl gap-2 p-4" onSubmit={submitChat}>
        <Input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="Message your knowledge base..." />
        <Button disabled={isChatting} type="submit">
          {isChatting ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageCircle className="h-4 w-4" />}
        </Button>
      </form>
    </main>
  );
}
