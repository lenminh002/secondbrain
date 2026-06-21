import { FormEvent } from "react";
import { Bot, GitBranch, Loader2, MessageCircle, ChevronRight, ChevronLeft } from "lucide-react";

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
  isMinimized,
  toggleMinimize,
}: {
  chatInput: string;
  chatLog: ChatMessage[];
  isChatting: boolean;
  setChatInput: (value: string) => void;
  submitChat: (event: FormEvent<HTMLFormElement>) => void;
  isMinimized?: boolean;
  toggleMinimize?: () => void;
}) {
  if (isMinimized) {
    return (
      <Card className="flex h-full min-h-0 flex-col rounded-none border-0 border-l shadow-none lg:rounded-none bg-muted/20 items-center py-4">
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
    <Card className="flex h-full min-h-0 flex-col rounded-none border-0 border-l shadow-none lg:rounded-none relative">
      <CardHeader className="border-b pr-14">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          <CardTitle>The Librarian</CardTitle>
        </div>
        <CardDescription>Ask across notes, graph nodes, and generated posts.</CardDescription>
        {toggleMinimize && (
          <Button variant="ghost" size="icon" className="absolute top-4 right-4" onClick={toggleMinimize}>
            <ChevronRight className="h-5 w-5 text-muted-foreground" />
          </Button>
        )}
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
            <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
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
