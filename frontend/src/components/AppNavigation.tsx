import type { ReactNode } from "react";
import { useState } from "react";
import {
  BadgeCheck,
  BookOpen,
  CircleUserRound,
  Compass,
  GitBranch,
  Home,
  Lock,
  MessageCircle,
  PenLine,
  Search,
  Trash2,
  Upload,
} from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { AccountRecord, ActiveView, NotesMode } from "@/types";

export function Logo() {
  return (
    <div className="flex items-center gap-2">
      <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-primary text-primary-foreground">
        <PenLine className="h-5 w-5" />
      </div>
      <span className="brand text-xl leading-none">Second-Brain</span>
    </div>
  );
}

function SearchDialog({ onSearch }: { onSearch: (query: string) => void }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [history, setHistory] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem("recentSearches") || "[]");
    } catch {
      return [];
    }
  });

  function runSearch(value: string) {
    const trimmed = value.trim();
    if (!trimmed) return;
    const updated = [trimmed, ...history.filter((item) => item !== trimmed)].slice(0, 5);
    localStorage.setItem("recentSearches", JSON.stringify(updated));
    setHistory(updated);
    setQuery("");
    setOpen(false);
    onSearch(trimmed);
  }

  return (
    <Dialog onOpenChange={setOpen} open={open}>
      <DialogTrigger asChild>
        <Button size="icon" variant="ghost">
          <Search className="h-5 w-5" />
          <span className="sr-only">Search</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[460px]">
        <DialogHeader>
          <DialogTitle>Search</DialogTitle>
        </DialogHeader>
        <form className="relative mt-2" onSubmit={(event) => { event.preventDefault(); runSearch(query); }}>
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" onChange={(event) => setQuery(event.target.value)} placeholder="Search your knowledge..." value={query} />
        </form>
        <div className="mt-2">
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-sm font-medium">Recent searches</h4>
            {!!history.length && (
              <Button onClick={() => { setHistory([]); localStorage.removeItem("recentSearches"); }} size="icon" variant="ghost">
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
          <ScrollArea className="max-h-[220px]">
            <ul className="space-y-1">
              {history.length ? (
                history.map((item, index) => (
                  <li key={`${item}-${index}`}>
                    <Button className="w-full justify-start" onClick={() => runSearch(item)} variant="ghost">
                      <Search className="mr-2 h-4 w-4" />
                      {item}
                    </Button>
                  </li>
                ))
              ) : (
                <li className="px-1 text-sm text-muted-foreground">No recent searches.</li>
              )}
            </ul>
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function TopBar({
  account,
  activeView,
  setActiveView,
  onSearch,
}: {
  account: AccountRecord | null;
  activeView: ActiveView;
  setActiveView: (view: ActiveView) => void;
  onSearch: (query: string) => void;
}) {
  const tabValue = activeView === "home" ? "private" : activeView === "notes" ? "explore" : "";

  return (
    <header className="container mx-auto px-4 py-4 flex flex-col lg:flex-row items-center justify-between">
      <Logo />

      <div className="flex items-center gap-2">
        <SearchDialog onSearch={onSearch} />
        <Button className="rounded-full" onClick={() => setActiveView("profile")} size="icon" variant="ghost">
          <Avatar className="h-8 w-8">
            {account?.avatar_url && <AvatarImage alt={account.name} className="object-cover object-center" src={account.avatar_url} />}
            <AvatarFallback>{account?.initials || ""}</AvatarFallback>
          </Avatar>
        </Button>
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
  postDrawer?: ReactNode;
};

export function SidebarNav({
  account,
  activeView,
  notesMode,
  setActiveView,
  setNotesMode,
  postDrawer,
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
      <div className="mb-4 flex items-center gap-3 px-2">
        <Avatar>
          {account?.avatar_url && <AvatarImage alt={account.name} className="object-cover object-center" src={account.avatar_url} />}
          <AvatarFallback>{account?.initials || ""}</AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <div className="flex items-center">
            <p className="truncate font-medium">{account?.name || "Guest User"}</p>
            <BadgeCheck className="ml-1 h-4 w-4 shrink-0 text-blue-500" />
          </div>
          <p className="truncate text-xs text-muted-foreground">@{account?.handle || "guest"}</p>
        </div>
      </div>

      <nav className="flex flex-grow flex-col items-stretch space-y-1">
        {items.map((item) => (
          <Button
            className="w-full justify-start"
            key={item.label}
            onClick={item.action}
            variant={item.active ? "secondary" : "ghost"}
          >
            <item.icon className="mr-2 h-4 w-4" />
            <span>{item.label}</span>
          </Button>
        ))}
      </nav>

      <div className="pt-4">{postDrawer}</div>
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
