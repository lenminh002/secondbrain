import { Search, LogOut } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import type { AccountRecord } from "@/types";
import { Logo } from "./Logo";

export function TopBar({ account }: { account: AccountRecord | null }) {
  const { logout } = useAuth();

  return (
    <header className="sticky top-0 z-30 flex h-[74px] items-center justify-between border-b bg-background/95 px-5 backdrop-blur">
      <Logo account={account} />
      <div className="hidden w-full max-w-md items-center gap-2 rounded-full border bg-muted/35 px-3 py-2 md:flex">
        <Search className="h-4 w-4 text-muted-foreground" />
        <input className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground" placeholder="Search notes, concepts, posts..." />
      </div>
      <div className="flex items-center gap-3">
        {account && (
          <div className="hidden flex-col items-end text-right text-xs md:flex">
            <span className="font-semibold text-foreground">{account.name}</span>
            <span className="text-muted-foreground">@{account.handle}</span>
          </div>
        )}
        <Avatar>
          {account?.avatar_url && <AvatarImage alt={account.name} src={account.avatar_url} />}
          <AvatarFallback>{account?.initials || ""}</AvatarFallback>
        </Avatar>
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground hover:text-destructive transition-colors shrink-0"
          onClick={() => void logout()}
          title="Sign Out"
        >
          <LogOut className="h-4 w-5" />
        </Button>
      </div>
    </header>
  );
}
