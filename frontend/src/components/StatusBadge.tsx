import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { SourceStatus } from "@/types";

export function StatusBadge({ status }: { status: SourceStatus }) {
  const variant = status === "failed" ? "destructive" : status === "ready" ? "default" : "secondary";
  return (
    <Badge className={cn("capitalize shrink-0", status === "processing" && "text-muted-foreground")} variant={variant}>
      {status === "processing" && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
      {status}
    </Badge>
  );
}
