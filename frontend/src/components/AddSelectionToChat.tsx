import { useEffect, useState } from "react";
import { MessageCirclePlus } from "lucide-react";

import { Button } from "@/components/ui/button";

const SURFACE_SELECTOR = "[data-add-to-chat-surface='true']";

type SelectionState = {
  text: string;
  x: number;
  y: number;
};

function quoteForChat(text: string) {
  return text
    .trim()
    .split(/\r?\n/)
    .map((line) => `> ${line}`)
    .join("\n");
}

function selectionFromWindow(): SelectionState | null {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed) return null;

  const text = selection.toString().trim();
  if (!text) return null;

  const anchorNode = selection.anchorNode;
  const focusNode = selection.focusNode;
  const anchorElement = anchorNode instanceof Element ? anchorNode : anchorNode?.parentElement;
  const focusElement = focusNode instanceof Element ? focusNode : focusNode?.parentElement;
  const anchorSurface = anchorElement?.closest(SURFACE_SELECTOR);
  const focusSurface = focusElement?.closest(SURFACE_SELECTOR);

  if (!anchorSurface || !focusSurface || anchorSurface !== focusSurface) return null;

  const range = selection.getRangeAt(0);
  const rect = range.getBoundingClientRect();
  if (!rect.width && !rect.height) return null;

  return {
    text,
    x: Math.min(window.innerWidth - 148, Math.max(12, rect.left + rect.width / 2 - 62)),
    y: Math.max(12, rect.top - 44),
  };
}

export function AddSelectionToChat({
  onAdd,
}: {
  onAdd: (quotedText: string) => void;
}) {
  const [selectionState, setSelectionState] = useState<SelectionState | null>(null);

  useEffect(() => {
    function updateSelection() {
      window.setTimeout(() => setSelectionState(selectionFromWindow()), 0);
    }

    document.addEventListener("selectionchange", updateSelection);
    window.addEventListener("scroll", updateSelection, true);
    window.addEventListener("resize", updateSelection);

    return () => {
      document.removeEventListener("selectionchange", updateSelection);
      window.removeEventListener("scroll", updateSelection, true);
      window.removeEventListener("resize", updateSelection);
    };
  }, []);

  if (!selectionState) return null;

  return (
    <Button
      className="fixed z-50 h-9 gap-2 rounded-full shadow-lg"
      onMouseDown={(event) => event.preventDefault()}
      onClick={() => {
        onAdd(quoteForChat(selectionState.text));
        window.getSelection()?.removeAllRanges();
        setSelectionState(null);
      }}
      size="sm"
      style={{ left: selectionState.x, top: selectionState.y }}
      type="button"
    >
      <MessageCirclePlus className="h-4 w-4" />
      Add to Chat
    </Button>
  );
}
