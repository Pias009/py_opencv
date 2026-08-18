# Design

<!-- impeccable:design-schema 1 -->

## Visual World

Dark operator console. Restrained color strategy: near-black neutrals carry the whole surface, one blue accent marks action and identity, one orange pairs with it only in the gradient brand mark and the progress-bar fill. Good/bad signal colors (green/red) are reserved for status only, never decorative.

## Tokens

```css
--bg: #0f1115;
--card: #171a21;
--border: #2a2f3a;
--text: #e6e9ef;
--text-dim: #9aa3b2;
--accent: #4f8cff;
--accent-2: #ff7a45;
--good: #3ddc84;
--bad: #ff5c5c;
```

Font: system stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`) — an Operate surface, workhorse UI face is correct, no display face.

Radius: 12px on cards/sidebar blocks, 8-9px on inputs/buttons/brand mark. Border: 1px solid `--border` throughout, no shadows — flat dark-mode dashboard, not elevated glass.

## Layout

Two-column shell (`grid-template-columns: 280px 1fr`): a sticky left sidebar (live counts, always visible) and a scrolling main stage (upload, video preview, report, history) — the operator-console pattern this build introduced. Below 860px the sidebar becomes a static, wrapped row above the stage; below 480px it stacks to a single column. Tables that can overflow (history) sit inside `.table-scroll` (`overflow-x: auto`) so mobile never breaks the page's own horizontal scroll.

## Components

- **Sidebar blocks** (`.side-block`): card-styled panels, one per data group (total, per-direction, per-category, engine metadata). Each carries an uppercase `.side-label` kicker (0.72rem, tracked, dimmed) — the recurring "kicker + value" grammar used for every stat in this system.
- **Live status dot** (`.side-status.is-live`): a small glowing green dot + soft ring (`box-shadow` halo) prefixing the status text while a job runs; disappears once finished. This is the one "alive" signal in an otherwise static, flat system — use it only for genuinely live/in-progress state, never decoratively.
- **Line rows**: a colored dot (from a fixed 6-color sequence shared with any future per-line UI) + name on the left, `in N · out N` right-aligned in dimmed tabular numerals.
- **Download buttons** (`.download-btn` / `.download-btn-alt`): primary (filled accent, for PDF — the default hand-off format) and secondary (outlined, for Excel) pair, both carrying a small pill-badge file-type label (`.download-icon`) instead of an icon font/SVG.
- **Drop zone**: dashed border, brightens to accent on hover/dragover — inherited unchanged from the original upload surface.
- **Progress bar**: gradient fill (`accent` → `accent-2`) — the only place the second accent color appears outside the brand mark, reserved for "work in progress" only.

## Motion

Minimal, functional only: `opacity`/`border-color` transitions on hover (0.15s), progress-bar `width` transition (0.2s ease, inherited from the original build — an accepted layout-property transition on a single simple bar, not worth the complexity of a transform-based rework for this surface). No entrance animation, no decorative motion — an Operate surface stays out of the way of the task.

## Content Rules

- Sidebar numbers always render in `font-variant-numeric: tabular-nums` so live-updating digits don't shift layout.
- Category/line rows are hidden (not empty-stated) until real data exists — an operator glancing at a fresh page sees only "Total counted: 0 / Waiting for a video…", not empty panels.
- Report card shows only after a job finishes successfully; a cancelled or errored run never gets download buttons.
