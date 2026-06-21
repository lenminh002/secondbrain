import { PenLine } from "lucide-react";

export function Logo() {
  return (
    <div className="flex items-center gap-3">
      <div className="grid h-9 w-9 place-items-center rounded-lg bg-primary text-primary-foreground">
        <PenLine className="h-5 w-5" />
      </div>
      <div className="text-xl font-black leading-none tracking-tight">Second Brain</div>
    </div>
  );
}
