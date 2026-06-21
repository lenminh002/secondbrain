import { Button } from "@/components/ui/button";
import { mobileItems } from "@/lib/navigation";
import type { ActiveView } from "@/types";

type MobileNavProps = {
  activeView: ActiveView;
  setActiveView: (view: ActiveView) => void;
};

export function MobileNav({ activeView, setActiveView }: MobileNavProps) {
  return (
    <nav className="mobile-bottom-nav fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 gap-2 border-t bg-background p-3 lg:hidden">
      {mobileItems.map((item) => (
        <Button
          key={item.label}
          className="h-12 text-base"
          onClick={() => setActiveView(item.view)}
          variant={activeView === item.view ? "default" : "outline"}
        >
          <item.icon className="h-5 w-5" />
          {item.label}
        </Button>
      ))}
    </nav>
  );
}
