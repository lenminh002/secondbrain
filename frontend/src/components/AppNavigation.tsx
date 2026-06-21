import {
  Bell,
  BookOpen,
  CircleUserRound,
  Compass,
  GitBranch,
  Home,
  Menu,
  PenLine,
  Search,
  Settings,
  Upload,
} from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { AccountRecord, ActiveView, NotesMode } from "@/types";

export function Logo({ account }: { account: AccountRecord | null }) {
  return (
    <div className="flex items-center gap-3">
      <div className="grid h-9 w-9 place-items-center rounded-lg bg-primary text-primary-foreground">
        <PenLine className="h-5 w-5" />
      </div>
      <div>
        <div className="text-xl font-black tracking-tight">{account?.name || "Profile"}</div>
        <div className="text-xs text-muted-foreground">{account ? `@${account.handle}` : "Loading account"}</div>
      </div>
    </div>
  );
}

export function TopBar({ account }: { account: AccountRecord | null }) {
  return (
    <header className="sticky top-0 z-30 flex h-[74px] items-center justify-between border-b bg-background/95 px-5 backdrop-blur">
      <Logo account={account} />
      <div className="hidden w-full max-w-md items-center gap-2 rounded-full border bg-muted/35 px-3 py-2 md:flex">
        <Search className="h-4 w-4 text-muted-foreground" />
        <input className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground" placeholder="Search notes, concepts, posts..." />
      </div>
      <div className="flex items-center gap-3">
        <Avatar>
          {account?.avatar_url && <AvatarImage alt={account.name} src={account.avatar_url} />}
          <AvatarFallback>{account?.initials || ""}</AvatarFallback>
        </Avatar>
      </div>
    </header>
  );
}

type NavProps = {
  account: AccountRecord | null;
  activeView: ActiveView;
  notesMode: NotesMode;
  setActiveView: (view: ActiveView) => void;
  setNotesMode: (mode: NotesMode) => void;
  isMinimized: boolean;
  toggleMinimize: () => void;
};

export function SidebarNav({
  account,
  activeView,
  notesMode,
  setActiveView,
  setNotesMode,
  isMinimized,
  toggleMinimize,
}: NavProps) {
  const items = [
    { label: "Home", icon: Home, active: activeView === "home", action: () => setActiveView("home") },
    { label: "Memories", icon: BookOpen, active: activeView === "notes" && notesMode === "note", action: () => { setActiveView("notes"); setNotesMode("note"); } },
    { label: "Graph", icon: GitBranch, active: activeView === "notes" && notesMode === "graph", action: () => { setActiveView("notes"); setNotesMode("graph"); } },
    { label: "Profile", icon: CircleUserRound, active: activeView === "profile", action: () => setActiveView("profile") },
  ];

  const ingestButton = (
    <Button
      className={cn(
        "w-full transition-all duration-300",
        isMinimized ? "justify-center px-0 h-10 w-10 mx-auto rounded-full" : "gap-2"
      )}
      onClick={() => setActiveView("ingest")}
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
      {/* Menu Toggle Button at Top Left */}
      <div className={cn("mb-6 flex items-center", isMinimized ? "justify-center" : "justify-start")}>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              className="h-10 w-10 rounded-md text-muted-foreground hover:text-foreground shrink-0"
              onClick={toggleMinimize}
              size="icon"
              variant="ghost"
            >
              <Menu className="h-5 w-5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">
            {isMinimized ? "Expand menu" : "Collapse menu"}
          </TooltipContent>
        </Tooltip>
      </div>


      <nav className="space-y-1 flex-grow flex flex-col items-stretch">
        {items.map((item) => {
          const buttonContent = (
            <Button
              className={cn(
                "transition-all duration-300",
                isMinimized ? "h-10 w-10 mx-auto justify-center" : "w-full justify-start gap-3 text-base",
                item.active ? "text-foreground" : "text-muted-foreground"
              )}
              key={item.label}
              onClick={item.action}
              variant={item.active ? "secondary" : "ghost"}
              size={isMinimized ? "icon" : "default"}
            >
              <item.icon className="h-5 w-5 shrink-0" />
              {!isMinimized && <span>{item.label}</span>}
            </Button>
          );

          if (isMinimized) {
            return (
              <Tooltip key={item.label}>
                <TooltipTrigger asChild>{buttonContent}</TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            );
          }

          return <div key={item.label}>{buttonContent}</div>;
        })}

        {[
          { label: "Explore", icon: Compass },
          { label: "Notifications", icon: Bell },
          { label: "Settings", icon: Settings },
        ].map((item) => {
          const buttonContent = (
            <Button
              className={cn(
                "transition-all duration-300",
                isMinimized ? "h-10 w-10 mx-auto justify-center" : "w-full justify-start gap-3 text-base text-muted-foreground"
              )}
              disabled
              key={item.label}
              variant="ghost"
              size={isMinimized ? "icon" : "default"}
            >
              <item.icon className="h-5 w-5 shrink-0" />
              {!isMinimized && <span>{item.label}</span>}
            </Button>
          );

          if (isMinimized) {
            return (
              <Tooltip key={item.label}>
                <TooltipTrigger asChild>{buttonContent}</TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            );
          }

          return <div key={item.label}>{buttonContent}</div>;
        })}
      </nav>

      <div className="pt-4 border-t">
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

export function MobileNav({ activeView, setActiveView }: Pick<NavProps, "activeView" | "setActiveView">) {
  return (
    <nav className="mobile-bottom-nav fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 gap-2 border-t bg-background p-3 lg:hidden">
      <Button className="h-12 text-base" onClick={() => setActiveView("home")} variant={activeView === "home" ? "default" : "outline"}>
        <Home className="h-5 w-5" />
        Home
      </Button>
      <Button className="h-12 text-base" onClick={() => setActiveView("notes")} variant={activeView === "notes" ? "default" : "outline"}>
        <BookOpen className="h-5 w-5" />
        Memories
      </Button>
      <Button className="h-12 text-base" onClick={() => setActiveView("ingest")} variant={activeView === "ingest" ? "default" : "outline"}>
        <Upload className="h-5 w-5" />
        Ingest
      </Button>
      <Button className="h-12 text-base" onClick={() => setActiveView("profile")} variant={activeView === "profile" ? "default" : "outline"}>
        <CircleUserRound className="h-5 w-5" />
        Profile
      </Button>
    </nav>
  );
}
