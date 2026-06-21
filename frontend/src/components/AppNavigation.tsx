import {
  Bell,
  BookOpen,
  CircleUserRound,
  Compass,
  GitBranch,
  Home,
  LogOut,
  PenLine,
  Search,
  Settings,
  Upload,
} from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
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

export function TopBar({
  account,
  signOutUser,
}: {
  account: AccountRecord | null;
  signOutUser: () => Promise<void>;
}) {
  return (
    <header className="sticky top-0 z-30 flex h-[74px] items-center justify-between border-b bg-background/95 px-5 backdrop-blur">
      <Logo account={account} />
      <div className="hidden w-full max-w-md items-center gap-2 rounded-full border bg-muted/35 px-3 py-2 md:flex">
        <Search className="h-4 w-4 text-muted-foreground" />
        <input className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground" placeholder="Search notes, concepts, posts..." />
      </div>
      <div className="flex items-center gap-3">
        <Button className="hidden md:inline-flex" size="icon" variant="ghost">
          <Search className="h-5 w-5" />
        </Button>
        <Avatar>
          {account?.avatar_url && <AvatarImage alt={account.name} src={account.avatar_url} />}
          <AvatarFallback>{account?.initials || ""}</AvatarFallback>
        </Avatar>
        <Button onClick={() => void signOutUser()} size="icon" variant="ghost">
          <LogOut className="h-5 w-5" />
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
};

export function SidebarNav({ account, activeView, notesMode, setActiveView, setNotesMode }: NavProps) {
  const items = [
    { label: "Home", icon: Home, active: activeView === "home", action: () => setActiveView("home") },
    { label: "Notes", icon: BookOpen, active: activeView === "notes" && notesMode === "note", action: () => { setActiveView("notes"); setNotesMode("note"); } },
    { label: "Graph", icon: GitBranch, active: activeView === "notes" && notesMode === "graph", action: () => { setActiveView("notes"); setNotesMode("graph"); } },
    { label: "Profile", icon: CircleUserRound, active: activeView === "profile", action: () => setActiveView("profile") },
  ];

  return (
    <aside className="sticky top-[74px] hidden h-[calc(100vh-74px)] border-r bg-background px-5 py-7 lg:block">
      <div className="mb-8 flex items-center gap-3">
        <Avatar className="h-14 w-14">
          {account?.avatar_url && <AvatarImage alt={account.name} src={account.avatar_url} />}
          <AvatarFallback>{account?.initials || ""}</AvatarFallback>
        </Avatar>
        <div>
          <div className="font-semibold">{account?.name || "Loading"}</div>
          <div className="text-sm text-muted-foreground">{account ? `@${account.handle}` : "Loading account"}</div>
        </div>
      </div>
      <nav className="space-y-1">
        {items.map((item) => (
          <Button
            className={cn("w-full justify-start gap-3 text-base", item.active ? "text-foreground" : "text-muted-foreground")}
            key={item.label}
            onClick={item.action}
            variant={item.active ? "secondary" : "ghost"}
          >
            <item.icon className="h-5 w-5" />
            {item.label}
          </Button>
        ))}
        {[
          { label: "Explore", icon: Compass },
          { label: "Notifications", icon: Bell },
          { label: "Settings", icon: Settings },
        ].map((item) => (
          <Button className="w-full justify-start gap-3 text-base text-muted-foreground" disabled key={item.label} variant="ghost">
            <item.icon className="h-5 w-5" />
            {item.label}
          </Button>
        ))}
      </nav>
      <Button className="mt-6 w-full gap-2" onClick={() => setActiveView("digest")}>
        <Upload className="h-4 w-4" />
        Digest Source
      </Button>
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
        Notes
      </Button>
      <Button className="h-12 text-base" onClick={() => setActiveView("digest")} variant={activeView === "digest" ? "default" : "outline"}>
        <Upload className="h-5 w-5" />
        Digest
      </Button>
      <Button className="h-12 text-base" onClick={() => setActiveView("profile")} variant={activeView === "profile" ? "default" : "outline"}>
        <CircleUserRound className="h-5 w-5" />
        Profile
      </Button>
    </nav>
  );
}
