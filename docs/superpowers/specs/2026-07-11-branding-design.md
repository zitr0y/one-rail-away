# onestopeurope — brand & map identity (backlog item D)

Date: 2026-07-11. Decided interactively with the user (visual-companion session;
mockups persist in `.superpowers/brainstorm/1233204-1783797492/content/`).

## The system in one sentence

Two palettes with strict jobs: **EU duotone is the brand** (logo, chrome, buttons,
tagline), **viridis-reversed is the data** (travel-time buckets on the map). The
mascot bridges them: navy stroke, gold star.

## Fixed brand facts

- Name: **onestopeurope** (onestopeurope.eu)
- Tagline (fixed, verbatim): **"nonstopeurope with onestopeurope"**
- Personality: cute mascot, clean data-first product ("Duolingo-owl-meets-Positron")

## Color tokens

| Token | Value | Job |
|---|---|---|
| brand-navy | `#003399` | chrome, logo stroke, buttons, selected states |
| brand-gold | `#FFCC00` | logo star, tagline, small accents |
| bucket-0 (fastest) | `#FDE725` | reach lines/dots |
| bucket-1 | `#35B779` | reach lines/dots |
| bucket-2 | `#31688E` | reach lines/dots |
| bucket-3 (slowest) | `#440154` | reach lines/dots |
| land-light | `#F2EFE9` | warm-paper basemap land |
| water-light | `#CFE3F0` | basemap water (light) |
| land-dark | `#101C36` | deep-night basemap land |
| water-dark | `#0A1226` | basemap water (dark) |

Buckets were validated with the dataviz palette validator: CVD separation passes
(worst adjacent ΔE 24.6 deutan); as a sequential ramp the lightness span is
intentional. The EU duotone data ramp (`#FFD617 #E0A82E #4A74C9 #002F87`) was the
runner-up and stays "in mind" — it became the brand palette instead of the data
palette.

**Known tuning point:** bucket-0 yellow is ~1.2:1 against cream land. Resolve at
implementation with either a slightly deepened yellow or a hairline dark casing
on bucket-0 lines only — judged on the real map by the user (verification stays
data/text-based per project convention; visual verdicts are the user's).

## Logo & mascot — "Train on the line" (chosen sketch C0)

Single-stroke line-art train sitting ON the route line: the line runs in from the
left (with a hollow station dot), becomes the train's baseline, and exits right
(second station dot). Boxy rounded body, two hollow wheels, tiny dot-eyes + smile
near the nose, dotted window line, one gold star on the flank. Navy `#003399`
stroke, round caps, on transparent background.

Hand-crafted SVG, one source file, three variants:

1. **Full lockup** — mascot + `onestopeurope` wordmark (Barlow bold, navy) +
   tagline (gold italic): header and any landing/about surface.
2. **Mascot-only** — loading states, empty states.
3. **Favicon** — simplified thick-stroke version (~6-unit stroke, star bigger,
   face/window dropped); replaces the current leftover purple template
   `web/public/favicon.svg`.

Rejected variants (kept for the record): rounder/cuter body with yellow window
band ("weird" yellow), pre-bent body over a hill (bend didn't read), single
continuous stroke with wheel loops ("looks like it had a stroke").

## Map styling

- **Basemap light (default): warm paper.** Fork OpenFreeMap Positron style JSON
  into the repo as `web/public/mapstyle-light.json` (same OpenFreeMap tile
  source), retinted: land `#F2EFE9`, water `#CFE3F0`, muted roads/labels. This
  closes item D's "water should read differently from stations".
- **Basemap dark: deep night.** `web/public/mapstyle-dark.json`: land `#101C36`,
  water `#0A1226`, light labels. Viridis buckets glow on it unchanged.
- **`BUCKET_COLORS` in `web/src/lib/colors.ts`** becomes the viridis-reversed
  quad above; legend and anything else consuming it follows automatically.
- **Re-tune, don't redesign:** grey all-stations dots, capital stars, coverage
  veil tint, and journey dimming (0.04) get contrast-checked against both
  basemaps and adjusted per theme where needed.

## UI chrome & typography

- Navy `#003399` header bar: full lockup left, gold italic tagline (per the
  approved mockup).
- **Barlow** (DIN 1451 rail-signage tradition) everywhere; self-hosted woff2
  (no Google Fonts request at runtime). Weights: 400/600/700.
- Buttons/selected states navy with gold accents; panels warm white (light) /
  deep navy (dark).
- Dark mode follows `prefers-color-scheme` plus a manual toggle; chrome stays
  navy in both themes.

## Phasing

- **Phase 1 (this spec's implementation plan): light identity.** Basemap-light
  JSON, bucket recolor, logo/lockup/favicon SVGs, header chrome, Barlow,
  station-dot/veil/star re-tune on paper.
- **Phase 2: dark mode.** mapstyle-dark, theme toggle + `prefers-color-scheme`,
  per-theme layer colors and panel styles.
- **Phase 3 (backlog, explicitly out of scope):** mascot bends along the actual
  selected route geometry (animation), logo draw-itself-on animation. Related:
  item I (corridor bundling) shares the map-styling ground.

## Testing & verification

- Colors single-sourced in `colors.ts` (extend with brand/basemap tokens as
  needed by code; the style JSONs carry their own values).
- Pure helpers (theme → style URL, theme → per-layer color sets) unit-tested in
  the existing vitest pattern.
- No screenshot-based verification; state checks via DEV `window.__map` where
  useful; the user eyeballs visual results.
