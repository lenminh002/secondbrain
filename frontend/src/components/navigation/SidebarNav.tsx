import { Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { sidebarItems } from "@/lib/navigation";
import type { AccountRecord, ActiveView, NotesMode } from "@/types";
import { NavItem } from "./NavItem";

export type NavProps = {
  account: AccountRecord | null;
  activeView: ActiveView;
  notesMode: NotesMode;
  setActiveView: (view: ActiveView) => void;
  setNotesMode: (mode: NotesMode) => void;
  isMinimized: boolean;
  onIngestClick: () => void;
};

export function SidebarNav({
  activeView,
  notesMode,
  setActiveView,
  setNotesMode,
  isMinimized,
  onIngestClick,
}: NavProps) {
  const ingestButton = (
    <Button
      className={cn(
        "w-full transition-all duration-300",
        isMinimized ? "justify-center px-0 h-10 w-10 mx-auto rounded-full" : "gap-2"
      )}
      onClick={onIngestClick}
      size={isMinimized ? "icon" : "default"}
    >
      <Upload className="h-4 w-4 shrink-0" />
      {!isMinimized && <span>Ingest Source</span>}
    </Button>
  );

  return (
    <aside
      className={cn(
        "sticky top-[74px] hidden h-[calc(100vh-74px)] border-r bg-background py-7 lg:flex flex-col transition-all duration-300 ease-in-out",
        isMinimized ? "px-3" : "px-5"
      )}
    >
      <nav className="space-y-1 flex-grow flex flex-col items-stretch">
        {sidebarItems.map((item) => {
          const active = !item.disabled &&
            item.view === activeView &&
            (item.mode == null || item.mode === notesMode);

          const onClick = item.disabled ? undefined : () => {
            if (item.view) setActiveView(item.view);
            if (item.mode) setNotesMode(item.mode);
          };

          return (
            <NavItem
              key={item.label}
              label={item.label}
              icon={item.icon}
              isMinimized={isMinimized}
              active={active}
              disabled={item.disabled}
              onClick={onClick}
            />
          );
        })}
      </nav>
        <div className="pt-4">
          {isMinimized ? (
            <Tooltip>
              <TooltipTrigger asChild>{ingestButton}</TooltipTrigger>
              <TooltipContent side="right">Ingest Source</TooltipContent>
            </Tooltip>
          ) : (
            ingestButton
          )}
        </div>
    </aside>
  );
}
