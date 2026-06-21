import { Bell, BookOpen, Bot, CircleUserRound, GitBranch, Home, Settings, Upload } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { ActiveView, NotesMode } from "@/types";

export type SidebarItem = {
  label: string;
  icon: LucideIcon;
  view?: ActiveView;
  mode?: NotesMode;
  disabled?: boolean;
};

export const sidebarItems: SidebarItem[] = [
  { label: "Home", icon: Home, view: "home" },
  { label: "Memories", icon: BookOpen, view: "notes", mode: "note" },
  { label: "Graph", icon: GitBranch, view: "notes", mode: "graph" },
  { label: "Librarian", icon: Bot, view: "chat" },
  { label: "Notifications", icon: Bell, disabled: true },
  { label: "Settings", icon: Settings, disabled: true },
];

export type MobileItem = { label: string; icon: LucideIcon; view: ActiveView };

export const mobileItems: MobileItem[] = [
  { label: "Home", icon: Home, view: "home" },
  { label: "Memories", icon: BookOpen, view: "notes" },
  { label: "Ingest", icon: Upload, view: "ingest" },
  { label: "Librarian", icon: Bot, view: "chat" },
];
