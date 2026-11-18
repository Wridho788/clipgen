# 12 --- Design system (M1)

Visual direction from `clipgen-campaign-uiux-milestones.md` §5, checked with the
`ui-ux-pro-max` skill (style: Dark Mode OLED; typography: Inter; focus,
contrast, and reduced-motion rules). The skill's suggested pink primary and
"Hero-Centric" landing pattern were **not** used: the milestone document fixes
the violet/cyan palette, and this is an app workspace, not a landing page.

## Principles

- Dark creative workspace by default; light theme stays available (toggle in the left rail). A stored choice always wins.
- Video and clips are the focus; chrome stays quiet. No glow, gradients, or glassmorphism except the progress bar (violet to cyan) and the logo mark.
- Elevation comes from surface tone plus a 1px hairline, not shadows.
- Every interactive element has a visible focus ring (2px cyan, `:focus-visible`), a hit area of at least 40px, specific `transition-colors` (never `transition: all`), and respects `prefers-reduced-motion`.

## Tokens

Defined as RGB channels in `frontend/src/app/globals.css` (`:root` = light, `.dark` = dark) and exposed in `tailwind.config.js` so opacity utilities work (`bg-brand/15`).

| Token (Tailwind) | Dark | Light | Use |
|---|---|---|---|
| `canvas` | `#111318` | `#F6F7FB` | App background |
| `surface` | `#181B22` | `#FFFFFF` | Panels, rail |
| `elevated` | `#20232B` | `#F1F3F8` | Tiles, inputs on panels, hover |
| `line` / `line-strong` | `#2A2E39` / `#3A3F4D` | `#E2E5EE` / `#C9CEDB` | Hairlines, input borders |
| `ink` | `#F3F4F8` | `#111318` | Primary text |
| `ink-muted` | `#A3A9B8` | `#565D6D` | Secondary text |
| `ink-subtle` | `#7C8394` | `#6B7282` | Captions, meta |
| `brand` | `#8B5CF6` | same | Accents, selection, borders on hover |
| `brand-strong` | `#7C3AED` | `#6D28D9` | Filled buttons (white text >= 5.7:1) |
| `brand-soft` | `#A78BFA` | `#6D28D9` | Brand-coloured text and links |
| `accent` | `#22D3EE` | `#0891B2` | Focus ring, active/progress cues |

Legacy `slate-*` classes are re-pointed at the same neutrals in `tailwind.config.js`, so older components follow the palette without a rewrite. New code should use the semantic tokens above.

Shared component classes (`globals.css`): `.cg-btn`, `.cg-btn-primary` (press scale 0.96), `.cg-input`, `.cg-eyebrow`, `.cg-progress`, `.clipgen-panel`, and the status tones `.cg-alert` / `.cg-alert-warn` / `.cg-alert-info`. The alert classes replaced ~14 hand-written copies of the same rose/amber box, several of which had no dark variant.

## Typography

Inter Variable, self-hosted through `@fontsource-variable/inter` (no network at runtime). Headings use `text-wrap: balance`, body `text-wrap: pretty`, numbers that change use `tabular-nums`.

## Layout

- `AppShell`: left rail (240px) with Proyek and Campaign, theme toggle, account. On `/jobs/*` the rail collapses to icons so the preview and inspector keep their width. Below `lg` it becomes a top bar.
- Content width is capped at 1400px.
- Dashboard: header, status tiles, new project (upload + campaign picker), latest campaigns, system status, project cards (campaign pill and gradient progress; failed and cancelled projects use a solid colour).
- Campaign pages: list, import (paste, analyse, review, confirm), detail with version history. Findings use Ditemukan / Perlu review / Tidak ada badges, and anything ambiguous blocks saving until acknowledged.
- Job page: header carries the status badge and campaign pill. While a job runs, progress and the stage timeline lead the page; once it is finished they collapse into a `Detail pipeline & progres` disclosure so the clip rail and editor sit near the top. The clip rail uses small thumbnails (96-112px) because the full controls live in the selected clip's editor.

## Not done yet

- Editor internals (M6): colours, tabs, alerts, and buttons follow the tokens, and the inspector has a Campaign tab (rules in force + compliance findings grouped by status, no percentage). Still missing: timeline tracks and the Campaign Assistant panel with preview/apply/undo.
- Wireframes for Generated Clips and Clip Workspace beyond the existing layouts.
- Contrast was checked by token choice, not with an automated audit.
