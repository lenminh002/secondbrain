import { Button } from "@/components/ui/button";
import { mobileItems } from "@/lib/navigation";
import type { ActiveView } from "@/types";
import { cn } from "@/lib/utils";

type MobileNavProps = {
  activeView: ActiveView;
  setActiveView: (view: ActiveView) => void;
  onIngestClick: () => void;
};

export function MobileNav({ activeView, setActiveView, onIngestClick }: MobileNavProps) {
  return (
    <nav className="mobile-bottom-nav fixed bottom-0 left-0 right-0 z-40 border-t bg-background lg:hidden">
      <div className="flex justify-around items-center h-14 px-2">
        {mobileItems.map((item) => {
          const active = activeView === item.view;
          const onClick = item.view === "ingest"
            ? onIngestClick
            : () => setActiveView(item.view);

          return (
            <Button
              key={item.label}
              className={cn(
                "transition-all duration-300 h-10 w-10 rounded-md",
                active ? "text-foreground" : "text-muted-foreground hover:!bg-muted hover:!text-foreground"
              )}
              onClick={onClick}
              variant={active ? "secondary" : "ghost"}
              size="icon"
            >
              <item.icon className="h-5 w-5" />
              <span className="sr-only">{item.label}</span>
            </Button>
          );
        })}
      </div>
    </nav>
  );
}
