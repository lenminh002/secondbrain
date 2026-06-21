import {
  BookOpen,
  CircleUserRound,
  GitBranch,
  Home,
  MessageCircle,
  PenLine,
  Search,
  Upload,
} from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AccountRecord, ActiveView, NotesMode } from "@/types";

export function Logo() {
  return (
    <div className="flex items-center gap-3">
      <div className="grid h-8 w-8 place-items-center rounded-md bg-primary text-primary-foreground">
        <PenLine className="h-5 w-5" />
      </div>
      <div className="brand text-xl leading-none">Second-Brain</div>
    </div>
  );
}

export function TopBar({ account }: { account: AccountRecord | null }) {
  return (
    <header className="sticky top-0 z-30 flex h-[74px] items-center justify-between bg-background px-4 lg:px-6">
      <Logo />
      <div className="hidden w-full max-w-sm items-center gap-2 rounded-md bg-muted px-3 py-2 md:flex">
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
};

export function SidebarNav({
  account,
  activeView,
  notesMode,
  setActiveView,
  setNotesMode,
}: NavProps) {
  const items = [
    { label: "Home", icon: Home, active: activeView === "home", action: () => setActiveView("home") },
    { label: "Notes", icon: BookOpen, active: activeView === "notes" && notesMode === "note", action: () => { setActiveView("notes"); setNotesMode("note"); } },
    { label: "Graph", icon: GitBranch, active: activeView === "notes" && notesMode === "graph", action: () => { setActiveView("notes"); setNotesMode("graph"); } },
    { label: "Chat", icon: MessageCircle, active: activeView === "chat", action: () => setActiveView("chat") },
    { label: "Profile", icon: CircleUserRound, active: activeView === "profile", action: () => setActiveView("profile") },
  ];

  return (
    <aside className="sticky top-[74px] hidden h-[calc(100vh-74px)] flex-col bg-background px-5 py-5 lg:flex">
      <div className="mb-5 flex items-center gap-3">
        <Avatar className="h-14 w-14">
          {account?.avatar_url && <AvatarImage alt={account.name} src={account.avatar_url} />}
          <AvatarFallback>{account?.initials || ""}</AvatarFallback>
        </Avatar>
        <div className="overflow-hidden">
          <div className="font-semibold">{account?.name || "Loading"}</div>
          <div className="text-sm text-muted-foreground">{account ? `@${account.handle}` : "Loading account"}</div>
        </div>
      </div>

      <nav className="flex flex-grow flex-col items-stretch space-y-1">
        {items.map((item) => (
          <Button
            className={cn("w-full justify-start gap-3 text-base", item.active ? "text-foreground" : "text-muted-foreground")}
            key={item.label}
            onClick={item.action}
            variant={item.active ? "secondary" : "ghost"}
          >
            <item.icon className="h-5 w-5 shrink-0" />
            <span>{item.label}</span>
          </Button>
        ))}
      </nav>

      <div className="pt-4">
        <Button className="w-full gap-2" onClick={() => setActiveView("digest")}>
          <Upload className="h-4 w-4 shrink-0" />
          <span>Digest Source</span>
        </Button>
      </div>
    </aside>
  );
}

export function MobileNav({ activeView, setActiveView }: Pick<NavProps, "activeView" | "setActiveView">) {
  return (
    <nav className="mobile-bottom-nav fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 bg-background px-2 py-2 lg:hidden">
      <Button className="h-12 flex-col gap-1 rounded-md text-[11px] font-medium" onClick={() => setActiveView("home")} variant={activeView === "home" ? "secondary" : "ghost"}>
        <Home className="h-5 w-5" />
        Home
      </Button>
      <Button className="h-12 flex-col gap-1 rounded-md text-[11px] font-medium" onClick={() => setActiveView("notes")} variant={activeView === "notes" ? "secondary" : "ghost"}>
        <BookOpen className="h-5 w-5" />
        Notes
      </Button>
      <Button className="h-12 flex-col gap-1 rounded-md text-[11px] font-medium" onClick={() => setActiveView("chat")} variant={activeView === "chat" ? "secondary" : "ghost"}>
        <MessageCircle className="h-5 w-5" />
        Chat
      </Button>
      <Button className="h-12 flex-col gap-1 rounded-md text-[11px] font-medium" onClick={() => setActiveView("digest")} variant={activeView === "digest" ? "secondary" : "ghost"}>
        <Upload className="h-5 w-5" />
        Digest
      </Button>
      <Button className="h-12 flex-col gap-1 rounded-md text-[11px] font-medium" onClick={() => setActiveView("profile")} variant={activeView === "profile" ? "secondary" : "ghost"}>
        <CircleUserRound className="h-5 w-5" />
        Profile
      </Button>
    </nav>
  );
}
