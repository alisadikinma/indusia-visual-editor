# Dashboard Design Tokens — Phase 1.4

> Translates plan §A.6 "Industrial Precision Dark" into actionable tokens
> for the Dashboard view. Status: ACTIVE. Update when shipping a new
> Dashboard variant.

---

## Tokens in play (subset of plan §A.6)

All tokens already live in `web/tailwind.config.js`. **Never hardcode hex
codes in Vue templates — always use the Tailwind class** (`bg-bg-base`,
`text-text-primary`, etc.).

| Role | Tailwind class | Hex | Use |
|---|---|---|---|
| App shell background | `bg-bg-deep` | `#020617` | `<body>`, full-page area |
| Panel / card surface | `bg-bg-elevated` | `#111827` | Project table card, dialog backdrop |
| Hover row | `bg-bg-hover` | `#1A2236` | Row hover state |
| Active selection | `bg-bg-active` | `#1E293B` | Selected row, focused input |
| Primary CTA | `bg-primary` | `#22C55E` | "New Project" button, "Save" |
| Primary hover | `bg-primary-hover` | `#16A34A` | Hover on green CTAs |
| Primary text | `text-text-primary` | `#F1F5F9` | Body copy, headings |
| Secondary text | `text-text-secondary` | `#94A3B8` | Empty state, meta info |
| Tertiary text | `text-text-tertiary` | `#64748B` | Timestamps, footer labels |
| Border | `border-border-default` | `#1E293B` | Table dividers, card outlines |
| Border focus | `border-border-focus` | `#3B82F6` | Input focus ring (3px) |

## Typography

| Element | Font + class | Size | Weight | Line-height |
|---|---|---|---|---|
| Page title ("Projects") | `font-sans` (IBM Plex Sans) | 28px | 700 | 1.2 |
| Section / table header | `font-sans` | 12px uppercase | 600 | 1.4 (tracking +0.05em) |
| Body text in table cells | `font-sans` | 14px | 400 | 1.5 |
| Data values (slugs, IDs) | `font-mono` (Fira Code) | 14px | 400 | 1.4 |
| Empty state copy | `font-sans` | 14px | 400 | 1.5 — `text-text-secondary` |
| Button label | `font-sans` | 13px uppercase | 600 | 1 (tracking +0.04em) |

## Status badge variants (4 project statuses)

A row's status column renders a pill-badge with the table below. **Always
pair the color with a text label** — color alone is not an accessible
indicator (plan §A.6 accessibility rule).

| Status | Background | Text color | Label | Notes |
|---|---|---|---|---|
| `drafting` | `bg-secondary/20` (= `rgba(59,130,246,0.2)`) | `text-secondary` (`#3B82F6`) | "Drafting" | Default for new projects |
| `training` | `bg-warning/20` | `text-warning` (`#F59E0B`) | "Training" | Add `animate-pulse` while M7 is running |
| `deployed` | `bg-success/20` | `text-success` (`#10B981`) | "Deployed" | Steady state |
| `failed` | `bg-danger/20` | `text-danger` (`#EF4444`) | "Failed" | Pair with a tooltip showing the failure reason in M9+ |

Pill shape: `rounded-full px-2.5 py-1 text-xs font-semibold tracking-wide`.

## Spacing scale (strict 8dp grid)

| Token | Tailwind | Px |
|---|---|---|
| --space-1 | `p-1` / `gap-1` | 4 |
| --space-2 | `p-2` | 8 |
| --space-3 | `p-3` | 12 |
| --space-4 | `p-4` | 16 |
| --space-5 | `p-5` | 20 |
| --space-6 | `p-6` | 24 |
| --space-8 | `p-8` | 32 |
| --space-10 | `p-10` | 40 |
| --space-12 | `p-12` | 48 |

Dashboard outer padding: `p-8` (32px desktop). Header bottom margin: `mb-6` (24px).

## Layout

```
┌──────────────────────────────────────────────────────────┐  bg-bg-deep
│  p-8                                                      │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  <h1>Projects</h1>             [+ New Project]      │  │  primary CTA
│  │                                                      │  │
│  │  ┌────────────────────────────────────────────────┐ │  │  bg-bg-elevated
│  │  │ NAME             SLUG          STATUS  UPDATED  │ │  │  card
│  │  │ ─────────────────────────────────────────────── │ │  │
│  │  │ NV80-017542      nv80-...      [Deploy] 2h ago  │ │  │  hover: bg-bg-hover
│  │  │ Board A          board-a       [Draft]  5m ago  │ │  │
│  │  └────────────────────────────────────────────────┘ │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

Empty state (no projects yet) — replaces the table:

```
┌─────────────────────────────────────┐
│                                     │
│   Belum ada project.                │  text-text-secondary
│   Mulai dengan upload BOM dan       │  font-sans 14px
│   Golden Sample.                    │
│                                     │
│   [+ Project Pertama]               │  same primary button
│                                     │
└─────────────────────────────────────┘
```

## Component patterns

### Primary button (`+ New Project`)
```html
<button class="bg-primary hover:bg-primary-hover text-text-on-primary
               rounded px-4 py-2 text-sm font-semibold uppercase tracking-wide
               transition-colors duration-150">
  + New Project
</button>
```

Note: `text-text-on-primary` (`#0F172A`) is dark text on green button — high
contrast per plan §A.6. **NOT white-on-green.**

### Status badge
```html
<span class="rounded-full px-2.5 py-1 text-xs font-semibold tracking-wide
             bg-secondary/20 text-secondary">
  Drafting
</span>
```

### Table row
```html
<tr class="border-b border-border-default hover:bg-bg-hover transition-colors">
  <td class="px-4 py-3 text-text-primary">{{ project.name }}</td>
  <td class="px-4 py-3 font-mono text-text-secondary">{{ project.slug }}</td>
  <td class="px-4 py-3"><StatusBadge :status="project.status" /></td>
  <td class="px-4 py-3 text-text-tertiary text-xs">{{ relativeTime }}</td>
</tr>
```

## Accessibility hard requirements

- All status badges include text label (color is decoration, not signal)
- Focus ring 3px solid `border-border-focus` (`#3B82F6`) on inputs + buttons
- Buttons have `aria-label` if icon-only
- Table has `<thead>` with proper `<th>` cells (semantic, not div)
- Empty state CTA `aria-describedby` points at the explanation copy

## Motion budget

- Hover transitions: 150ms ease-out (`transition-colors duration-150`)
- Dialog enter: 200ms cubic-bezier(0.4, 0, 0.2, 1)
- Dialog exit: 150ms ease-in
- Loading skeleton: shimmer pulse, infinite (only if fetch >300ms)
- Respect `prefers-reduced-motion: reduce` → drop all animations

## Anti-AI-slop checklist (must pass before commit)

- [ ] Zero emoji in UI strings (icons via Lucide only)
- [ ] No "leverage", "synergi", "revolusi" in Bahasa Indonesia copy
- [ ] No "game-changing", "powerful", "AI-driven" in English copy
- [ ] No `console.log` outside `if (import.meta.env.DEV)`
- [ ] No hardcoded hex codes (use Tailwind tokens only)
- [ ] No purple / pink accents (plan §A.6 forbidden palette)
