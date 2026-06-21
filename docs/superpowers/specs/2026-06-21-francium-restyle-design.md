# Frontend Restyle — Francium Clone, Zero Lines

**Date:** 2026-06-21
**Scope:** Pure re-skin of the existing frontend. No new features, no new components, no layout/behavior changes.

## Goal

Make the frontend match the visual identity of `github.com/coinleftt/francium`
(a standard shadcn/ui "slate" project) while removing **all UI chrome lines**
(borders, dividers, separators, card/input outlines, tab underlines). Graph
edges are exempt — they are data, not chrome.

User decisions captured during brainstorming:
- **Line scope:** Remove all UI chrome lines; replace with whitespace, soft
  shadows, and subtle background fills. Keep graph edges.
- **Fidelity:** Full francium clone — adopt francium's exact palette including
  its near-monochrome **gray accent**, and its **Borel** cursive brand wordmark.
- **No new features:** No dark/neon theme toggle, no added functionality.

## Strategy

Apply changes at the token + primitive level rather than editing every
component, so the global border rule and a few shadcn primitives do the work.

### 1. Palette → exact francium (shadcn slate) in `frontend/src/styles.css`

Update `@theme` tokens to francium's exact values:

| Token                 | New value (HSL)        |
| --------------------- | ---------------------- |
| `--color-foreground`  | `222.2 84% 4.9%`       |
| `--color-primary`     | `222.2 47.4% 11.2%`    |
| `--color-primary-foreground` | `210 40% 98%`   |
| `--color-secondary`   | `210 40% 96.1%`        |
| `--color-secondary-foreground` | `222.2 47.4% 11.2%` |
| `--color-muted`       | `210 40% 96.1%`        |
| `--color-muted-foreground` | `215.4 16.3% 46.9%` |
| `--color-accent`      | `210 40% 96.1%` (gray — replaces blue `213 94% 68%`) |
| `--color-accent-foreground` | `222.2 47.4% 11.2%` |
| `--color-destructive` | `0 84.2% 60.2%`        |
| `--color-border` / `--color-input` | `214.3 31.8% 91.4%` (retained; border made transparent in chrome) |
| `--color-ring`        | `222.2 84% 4.9%`       |
| `--radius-lg / md / sm` | `0.5rem / 0.375rem / 0.25rem` |

Card/popover backgrounds remain white.

### 2. Kill every chrome line

- `* { border-color: hsl(214 32% 91%) }` → **`border-color: transparent`**.
  Every `border` / `border-b` / `border-r` / `border-t` utility (top bar,
  sidebar, mobile nav, digest divider, cards, badges) renders invisible while
  keeping its layout box. No per-file border edits needed.
- `frontend/src/components/ui/separator.tsx`: `bg-border` → `bg-transparent`
  (separators become pure spacing).
- `frontend/src/components/ui/input.tsx` and `ui/textarea.tsx`: switch from
  border-defined fields to a **`bg-muted` fill** so they remain legible as
  fields without an outline.
- Cards keep their existing `shadow-sm`, so they float on whitespace instead of
  being boxed by a line (the francium "soft card" look).

### 3. Brand font (francium `.brand`)

- Import **Borel** from Google Fonts in `styles.css` and define a `.brand`
  utility (cursive family, matching francium's brand treatment).
- Apply `.brand` to the wordmark text in `frontend/src/components/AppNavigation.tsx`
  (`Logo`).

### 4. Graph node colors (in `styles.css`)

Gray (the new accent) would make nodes nearly invisible, so:
- `.graph-node circle` fill → `primary` navy (`222.2 47.4% 11.2%`).
- `.graph-node.source circle` → a lighter slate to stay distinguishable.
- Selected node keeps amber.
- Edges unchanged.

## Files touched

- `frontend/src/styles.css` (palette, transparent border, Borel import + `.brand`, graph colors)
- `frontend/src/components/ui/separator.tsx`
- `frontend/src/components/ui/input.tsx`
- `frontend/src/components/ui/textarea.tsx`
- `frontend/src/components/AppNavigation.tsx`

## Out of scope

- Dark / neon theme variants and any theme toggle.
- New components, layout changes, or behavior changes.
- Editing graph **edge** rendering (lines between nodes are data).

## Success criteria

- No visible borders/dividers/separators on cards, inputs, top bar, sidebar,
  mobile nav, tabs, or badges.
- Inputs/textareas remain visually distinguishable as fields (muted fill).
- Palette matches francium's slate tokens; accent is gray, not blue.
- Wordmark renders in the Borel cursive face.
- Graph nodes remain clearly visible; edges intact.
- `npm run build` (frontend) succeeds with no type errors.
