import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type NavItemProps = {
  label: string;
  icon: LucideIcon;
  isMinimized: boolean;
  active?: boolean;
  disabled?: boolean;
  onClick?: () => void;
};

export function NavItem({ label, icon: Icon, isMinimized, active, disabled, onClick }: NavItemProps) {
  const button = disabled ? (
    <Button
      className={cn(
        "transition-all duration-300",
        isMinimized ? "h-10 w-10 mx-auto justify-center" : "w-full justify-start gap-3 text-base text-muted-foreground"
      )}
      disabled
      variant="ghost"
      size={isMinimized ? "icon" : "default"}
    >
      <Icon className="h-5 w-5 shrink-0" />
      {!isMinimized && <span>{label}</span>}
    </Button>
  ) : (
    <Button
      className={cn(
        "transition-all duration-300",
        isMinimized ? "h-10 w-10 mx-auto justify-center" : "w-full justify-start gap-3 text-base",
        active ? "text-foreground" : "text-muted-foreground hover:!bg-muted hover:!text-foreground"
      )}
      onClick={onClick}
      variant={active ? "secondary" : "ghost"}
      size={isMinimized ? "icon" : "default"}
    >
      <Icon className="h-5 w-5 shrink-0" />
      {!isMinimized && <span>{label}</span>}
    </Button>
  );

  if (isMinimized) {
    return (
      <Tooltip key={label}>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent side="right">{label}</TooltipContent>
      </Tooltip>
    );
  }

  return <div>{button}</div>;
}
