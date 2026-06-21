import { RefreshCcw, RotateCcw, Search, ZoomIn, ZoomOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type GraphToolbarProps = {
  onRefresh: () => void;
  onFit: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  filterText: string;
  onFilterChange: (text: string) => void;
};

export function GraphToolbar({ onRefresh, onFit, onZoomIn, onZoomOut, onReset, filterText, onFilterChange }: GraphToolbarProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b bg-slate-50/70 px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full bg-slate-950" />
            Source
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full bg-sky-400" />
            Concept
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
            Tag
          </span>
        </div>
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="h-7 w-44 pl-7 text-xs"
            onChange={(e) => onFilterChange(e.target.value)}
            placeholder="Search nodes…"
            value={filterText}
          />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Button onClick={onRefresh} size="sm" variant="outline">
          <RefreshCcw className="h-3.5 w-3.5" />
          Refresh
        </Button>
        <Button onClick={onFit} size="sm" variant="outline">Fit Graph</Button>
        <Button onClick={onZoomIn} size="icon" variant="outline">
          <ZoomIn className="h-4 w-4" />
        </Button>
        <Button onClick={onZoomOut} size="icon" variant="outline">
          <ZoomOut className="h-4 w-4" />
        </Button>
        <Button onClick={onReset} size="icon" variant="outline">
          <RotateCcw className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
