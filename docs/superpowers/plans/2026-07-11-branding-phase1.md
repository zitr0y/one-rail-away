# Branding Phase 1 — Light Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved brand identity to the light theme: warm-paper basemap, viridis-reversed data palette, mascot-based logo/lockup/favicon SVGs, navy header bar with gold tagline, self-hosted Barlow font, and re-tuned map overlay contrast. Source of truth: `docs/superpowers/specs/2026-07-11-branding-design.md`.

**Architecture:** All changes are web-side. A new `mapstyle-light.json` replaces the remote Positron URL; `colors.ts` becomes the single source for brand + data tokens; three SVG files land in `web/public/`; `index.css` gains `@font-face` rules and header/chrome styles; `Map.tsx` and `dots.ts` get contrast adjustments. No Python pipeline changes.

**Tech Stack:** Vite + React 19 + vitest, MapLibre GL, self-hosted woff2 fonts.

## Global Constraints

(Carried over from `docs/superpowers/plans/2026-07-07-onestopeurope-restart.md`, still binding.)

- Python is uv-only: `uv run …`, never pip/venv.
- ruff clean, line length 100.
- TDD: failing test before implementation, for every change.
- Evidence-based comments for all data/config decisions (feeds.toml / aliases discipline).
- Commit after every task.
- `data/out/` is gitignored except the force-added samples: `data/out/stations.json`, `data/out/meta.json`, and the 5 `reach_x:db_fern:*.json` files listed by `git ls-files data/out`.
- Do not regress the stub-resolution design: (0,0)/missing-coordinate stops stay stubs at load; merge resolves them by unambiguous normalized-name match; unmatched → stripped + warned; trips <2 stops dropped.
- Long pipeline stages: run foreground with 600000 ms timeout, or background and WAIT for the notification (never poll).
- Subagent models: opus or sonnet only (never haiku).

---

### Task 1: Fork Positron basemap style as warm-paper `mapstyle-light.json`

**Files:**
- Create: `web/public/mapstyle-light.json`
- Create: `web/src/lib/mapstyle.test.ts`
- Create: `web/src/lib/mapstyle.ts`
- Modify: `web/src/components/Map.tsx` (swap style URL)

**Context for the agent:** The Map component at `web/src/components/Map.tsx:38` currently
loads the remote Positron style from `https://tiles.openfreemap.org/styles/positron`.
That URL serves a MapLibre style JSON document. We fork it into the repo so we can retint
land and water without depending on a remote file, while keeping the existing tile/glyph/sprite
sources pointing at OpenFreeMap.

**Brand spec tokens (source of truth — `docs/superpowers/specs/2026-07-11-branding-design.md`):**
- `land-light`: `#F2EFE9` (warm paper)
- `water-light`: `#CFE3F0`

- [ ] **Step 1: Fetch the Positron style JSON and save locally**

Run:
```bash
cd /home/aaron/Projects/personal/de-trains-speed-map
curl -sL https://tiles.openfreemap.org/styles/positron -o web/public/mapstyle-light.json
wc -c web/public/mapstyle-light.json
```
Expected: file written, size in the range 80–400 KB. The file is valid JSON containing
`"sources"`, `"glyphs"`, `"sprite"` keys and a `"layers"` array.

- [ ] **Step 2: Inspect the style and identify retint targets**

Read the downloaded `web/public/mapstyle-light.json`. Identify every layer whose
`paint` references a land/background color (typically `"fill-color"` on layers
named `background`, `landcover`, `landuse`, `park`, etc.) and every layer referencing
water color (`water`, `waterway`, etc.). Note the exact current hex values or HSL
expressions used.

The `"sources"`, `"glyphs"`, and `"sprite"` URLs MUST stay untouched — they point at
OpenFreeMap's tile server and are required for the map to render.

- [ ] **Step 3: Create the mapstyle helper and tests**

```typescript
// web/src/lib/mapstyle.ts
/**
 * Resolves the MapLibre style URL for the current theme.
 * Phase 1: light only. Phase 2 will add "dark" → mapstyle-dark.json.
 */
export function styleUrl(theme: "light"): string {
  return "/mapstyle-light.json";
}
```

```typescript
// web/src/lib/mapstyle.test.ts
import { describe, expect, it } from "vitest";
import { styleUrl } from "./mapstyle";

describe("styleUrl", () => {
  it("returns the local light style path", () => {
    expect(styleUrl("light")).toBe("/mapstyle-light.json");
  });
});
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npm test`
Expected: new test PASS; all existing tests PASS.

- [ ] **Step 5: Retint the style JSON**

Edit `web/public/mapstyle-light.json` applying these changes:

1. **Background layer** (usually first layer, `type: "background"`): set
   `"background-color"` to `"#F2EFE9"`.
2. **Land/landcover/landuse fill layers**: replace their fill-color with `"#F2EFE9"`
   (or a slightly lighter/darker shade for parks/green: `"#E8E5DC"` so parks don't
   vanish into the land — keep this subtle; the goal is muted, not invisible).
3. **Water layers** (`water`, `waterway`): replace fill-color with `"#CFE3F0"`,
   line-color for waterways with `"#B8D4E8"` (slightly deeper for thin lines).
4. **Road/boundary/label layers**: mute fill/line colors toward warm greys
   (e.g. `"#D5D2CA"` for minor roads, `"#C5C2B8"` for major) to keep the map
   readable but ensure the viridis data palette pops. Do NOT change label text
   colors to anything unreadable against `#F2EFE9`.
5. **Preserve all `"sources"`, `"glyphs"`, `"sprite"` keys exactly as fetched.**
   Do NOT change tile URLs, glyph URLs, or sprite URLs.

Verification: open the file and confirm `"sources"` still contains the original
OpenFreeMap tile URL(s), `"glyphs"` still points at the OpenFreeMap glyph endpoint,
and `"sprite"` is untouched.

- [ ] **Step 6: Swap the style URL in Map.tsx**

In `web/src/components/Map.tsx`, add `import { styleUrl } from "../lib/mapstyle";`
and change line 38 from:
```typescript
      style: "https://tiles.openfreemap.org/styles/positron",
```
to:
```typescript
      style: styleUrl("light"),
```

- [ ] **Step 7: Verify build + tests, commit**

```bash
cd web && npm test && npm run build && npm run lint
git add public/mapstyle-light.json src/lib/mapstyle.ts src/lib/mapstyle.test.ts src/components/Map.tsx
git commit -m "feat: fork Positron basemap as warm-paper mapstyle-light.json"
```

Expected: all tests PASS, build succeeds, lint clean. No test delta (new test added,
none broken).

---

### Task 2: Swap BUCKET_COLORS to viridis-reversed quad + brand tokens

**Files:**
- Modify: `web/src/lib/colors.ts`
- Create: `web/src/lib/colors.test.ts`

**Context for the agent:** `web/src/lib/colors.ts` currently exports:
```typescript
export const BUCKET_COLORS = ["#1a9850", "#fee08b", "#f46d43", "#d73027"] as const;
export const BUCKET_LABELS = ["< 3 h", "3–6 h", "6–10 h", "> 10 h"] as const;
```

Consumers: `Map.tsx` (line 15, `bucketColor` expression), `Legend.tsx` (imports both
arrays). These propagate automatically — no other files need changes for the color swap.

**Brand spec tokens (source of truth):**
- bucket-0 (fastest): `#FDE725`
- bucket-1: `#35B779`
- bucket-2: `#31688E`
- bucket-3 (slowest): `#440154`
- brand-navy: `#003399`
- brand-gold: `#FFCC00`

**Known tuning point (spec line 39–42):** bucket-0 yellow `#FDE725` is ~1.2:1 contrast
against cream land `#F2EFE9`. This task flags it explicitly; the user will judge on the
real map whether to deepen the yellow or add a hairline dark casing. This is NOT
auto-resolved — leave a `// TUNING POINT` comment in the code.

- [ ] **Step 1: Write the failing tests**

```typescript
// web/src/lib/colors.test.ts
import { describe, expect, it } from "vitest";
import { BUCKET_COLORS, BUCKET_LABELS, BRAND } from "./colors";

describe("BUCKET_COLORS", () => {
  it("has exactly 4 viridis-reversed entries", () => {
    expect(BUCKET_COLORS).toEqual(["#FDE725", "#35B779", "#31688E", "#440154"]);
  });

  it("matches BUCKET_LABELS length", () => {
    expect(BUCKET_COLORS.length).toBe(BUCKET_LABELS.length);
  });
});

describe("BRAND", () => {
  it("exports navy and gold", () => {
    expect(BRAND.navy).toBe("#003399");
    expect(BRAND.gold).toBe("#FFCC00");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npm test`
Expected: FAIL — `BRAND` is not exported from `./colors`; `BUCKET_COLORS` values
don't match the viridis quad yet.

- [ ] **Step 3: Update `web/src/lib/colors.ts`**

Replace the entire file content with:

```typescript
// Single source of truth for brand and data-palette colors.
// Spec: docs/superpowers/specs/2026-07-11-branding-design.md §Color tokens.

/** Viridis-reversed data palette — validated for CVD separation (worst adjacent
 *  ΔE 24.6 deutan). Consumed by Map.tsx bucket expression and Legend.tsx. */
export const BUCKET_COLORS = ["#FDE725", "#35B779", "#31688E", "#440154"] as const;
// TUNING POINT: bucket-0 yellow (#FDE725) is ~1.2:1 against cream land (#F2EFE9).
// Resolve at implementation with either a slightly deepened yellow or a hairline
// dark casing on bucket-0 lines only — judged on the real map by the user.

export const BUCKET_LABELS = ["< 3 h", "3–6 h", "6–10 h", "> 10 h"] as const;

/** EU duotone brand palette — chrome, logo, buttons, accents. */
export const BRAND = {
  navy: "#003399",
  gold: "#FFCC00",
} as const;
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npm test`
Expected: all PASS (new colors.test.ts passes; existing tests that import BUCKET_COLORS
still compile and pass because the type/length is unchanged).

- [ ] **Step 5: Verify build + lint, commit**

```bash
cd web && npm test && npm run build && npm run lint
git add src/lib/colors.ts src/lib/colors.test.ts
git commit -m "feat: viridis-reversed bucket colors + brand navy/gold tokens"
```

Expected: no test delta beyond the new test file. The legend and map lines now render in
the viridis palette. The user should eyeball bucket-0 yellow contrast against the
warm-paper basemap after Task 1 lands.

---

### Task 3: Logo SVG assets — full lockup, mascot-only, favicon

**Files:**
- Create: `web/public/logo-lockup.svg`
- Create: `web/public/logo-mascot.svg`
- Modify: `web/public/favicon.svg` (overwrite)

**Context for the agent:** The approved mascot is variant C0 ("train on the line").
The definitive SVG path data lives in two brainstorm files:

1. **Original sketch:** `.superpowers/brainstorm/1233204-1783797492/content/mascot-style.html`,
   card `data-choice='line-art'` (lines 77–90). The inline SVG inside that card's
   `.card-image` div contains the mascot paths at `viewBox="0 0 200 100"`.

2. **Refined baseline:** `.superpowers/brainstorm/1233204-1783797492/content/mascot-line-variations.html`,
   card `data-choice='c0-original'` (lines 8–21). Same viewBox, same paths — this is
   the canonical version.

**The C0 mascot SVG elements (exact path data to carry into the assets):**
```xml
<!-- Route line segments -->
<path d="M4 80 H38" stroke="#003399" stroke-width="3" fill="none" stroke-linecap="round"/>
<path d="M152 80 H196" stroke="#003399" stroke-width="3" fill="none" stroke-linecap="round"/>
<!-- Station dots on the line -->
<circle cx="14" cy="80" r="3.5" fill="#f6f4ee" stroke="#003399" stroke-width="2.5"/>
<circle cx="184" cy="80" r="3.5" fill="#f6f4ee" stroke="#003399" stroke-width="2.5"/>
<!-- Train body -->
<path d="M38 80 V46 Q38 36 48 36 H118 Q136 36 146 50 L156 68 Q160 76 152 80 Z" stroke="#003399" stroke-width="3" fill="none" stroke-linejoin="round"/>
<!-- Wheels -->
<circle cx="58" cy="80" r="7" stroke="#003399" stroke-width="2.5" fill="#f6f4ee"/>
<circle cx="126" cy="80" r="7" stroke="#003399" stroke-width="2.5" fill="#f6f4ee"/>
<!-- Dot eyes -->
<circle cx="122" cy="52" r="2.2" fill="#003399"/>
<circle cx="136" cy="56" r="2.2" fill="#003399"/>
<!-- Smile -->
<path d="M124 62 Q130 66 135 61" stroke="#003399" stroke-width="2" fill="none" stroke-linecap="round"/>
<!-- Dotted window line -->
<path d="M48 46 H100" stroke="#003399" stroke-width="2" stroke-dasharray="1 7" stroke-linecap="round"/>
<!-- Gold star -->
<text x="66" y="70" font-size="15" fill="#ffcc00" stroke="#eab308" stroke-width="0.5">★</text>
```

**Spec requirements (§ Logo & mascot):**

1. **Full lockup (`logo-lockup.svg`):** mascot + "onestopeurope" wordmark (Barlow Bold,
   navy `#003399`) + tagline "nonstopeurope with onestopeurope" (Barlow Italic, gold
   `#FFCC00`). Wordmark to the right of the mascot, tagline below the wordmark.
   Use `<text>` elements with `font-family="Barlow"`. **Limitation (accepted):** an SVG
   file referenced via `<img>` or opened standalone cannot fetch webfonts, so the lockup's
   text renders in the viewer's fallback font unless Barlow is installed locally. The
   lockup file is for contexts where that's acceptable (README, docs); the app header
   does NOT use it (see Task 4 — mascot SVG + HTML text instead). Converting the wordmark
   to paths is a future nicety, not Phase 1.

2. **Mascot-only (`logo-mascot.svg`):** The C0 train body, wheels, face, windows, star,
   station dots, and line segments. No wordmark. Transparent background.
   viewBox `0 0 200 100`.

3. **Favicon (`favicon.svg`):** Simplified thick-stroke version per spec: stroke-width ~6,
   star bigger, face/windows dropped. Replace the current purple lightning-bolt
   `web/public/favicon.svg`. viewBox `0 0 200 100`, should render legibly at 16×16px.

**Favicon SVG elements (simplified from C0):**
```xml
<!-- Thick-stroke train + line, no face/windows -->
<path d="M4 80 H38 M38 80 V46 Q38 36 48 36 H118 Q136 36 146 50 L156 68 Q160 76 152 80 Z M152 80 H196"
      stroke="#003399" stroke-width="6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<!-- Bigger gold star -->
<text x="60" y="74" font-size="30" fill="#ffcc00">★</text>
```
(This favicon SVG also exists in the brainstorm file, line 94, inside the favicon preview
span.)

- [ ] **Step 1: Create `web/public/logo-mascot.svg`**

Create the file using the exact C0 path data above. Use
`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">` as the root.
All fills that reference the paper background (`#f6f4ee`) should instead use
`"transparent"` or `"none"` for the station-dot fills and wheel fills, so the logo
works on any background. Actually, keep `#f6f4ee` for the station dots and wheels
since they need a visible fill to read as hollow; but note this is the paper color and
will need a per-theme variant in Phase 2.

- [ ] **Step 2: Create `web/public/logo-lockup.svg`**

Build the full lockup SVG:
- viewBox wide enough for mascot + text: approximately `0 0 520 100`.
- Place the mascot group at `x=0`. Use a `<g>` wrapping all mascot elements.
- Place `<text x="210" y="58" font-family="'Barlow', sans-serif" font-weight="700"
  font-size="32" fill="#003399">onestopeurope</text>`.
- Place `<text x="210" y="80" font-family="'Barlow', sans-serif" font-style="italic"
  font-weight="400" font-size="14" fill="#FFCC00">nonstopeurope with onestopeurope</text>`.
- Transparent background.

Verify by opening the SVG in a browser: the mascot appears left, wordmark right, tagline
below wordmark.

- [ ] **Step 3: Create `web/public/favicon.svg` (overwrite)**

Overwrite the existing purple lightning-bolt favicon with the simplified thick-stroke
train SVG described above. Root element:
`<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 200 100">`.

- [ ] **Step 4: Verify build, commit**

```bash
cd web && npm run build
# Verify all three SVGs are valid and in the dist output:
ls -la dist/logo-lockup.svg dist/logo-mascot.svg dist/favicon.svg 2>/dev/null || \
ls -la public/logo-lockup.svg public/logo-mascot.svg public/favicon.svg
git add public/logo-lockup.svg public/logo-mascot.svg public/favicon.svg
git commit -m "feat: C0 mascot SVG assets — lockup, mascot-only, favicon"
```

Expected: build succeeds; all three SVGs present in `web/public/`. No test delta (SVGs
are static assets, no logic to test).

---

### Task 4: Navy header bar with lockup + branded panel chrome

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/index.css`

**Context for the agent:** The current `App.tsx` (line 77–86) renders a white `.panel`
div with an `<h1>onestopeurope</h1>` and a grey `<p className="tagline">`. The spec
requires a navy `#003399` header bar with the mascot, white Barlow wordmark, and gold
italic tagline. **Do NOT use `logo-lockup.svg` via `<img>` here** — SVGs loaded through
`<img>` cannot fetch page webfonts, so its wordmark would never render in Barlow. Use
the mascot-only SVG plus HTML text, which does get Barlow from the page CSS.

The panel currently contains: `<h1>`, `<p.tagline>`, `<SearchBox>`, `<StopToggle>`,
`<TimeSlider>`, `<Legend>`, hint text, and error text. The branded design separates the
**header bar** (logo + tagline, navy background) from the **controls panel** (search,
toggle, slider, legend — warm white background).

**Brand tokens needed:**
- `brand-navy`: `#003399` (from `web/src/lib/colors.ts` as `BRAND.navy`)
- `brand-gold`: `#FFCC00` (from `web/src/lib/colors.ts` as `BRAND.gold`)

- [ ] **Step 1: Read current files to confirm structure**

Read `web/src/App.tsx` and `web/src/index.css` fully. Confirm the `.panel` class contains
all the controls (search, toggle, slider, legend). Note all CSS selectors that reference
`.panel` and `.tagline`.

- [ ] **Step 2: Update `web/src/App.tsx`**

Replace the header section (lines 77–86) with a two-part structure:

```tsx
      <header className="header-bar">
        <img src="/logo-mascot.svg" alt="" className="header-mascot" />
        <span className="header-wordmark">onestopeurope</span>
        <span className="header-tagline">nonstopeurope with onestopeurope</span>
      </header>
      <aside className="panel">
        <SearchBox onSelect={(s) => selectOrigin(s.id)} />
        <StopToggle value={maxTrains} onChange={setMaxTrains} />
        <TimeSlider value={maxMinutes} onChange={setMaxMinutes} />
        <Legend />
        {!reach && <p className="hint">Search or click a station to begin.</p>}
        {error && <p className="error">{error}</p>}
      </aside>
```

Remove the imports/usage of `<h1>` and `<p className="tagline">` from the header since
the lockup SVG already carries those.

- [ ] **Step 3: Update `web/src/index.css`**

Add the `.header-bar` styles and adjust `.panel`:

```css
.header-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 20;
  background: #003399;
  padding: 10px 16px;
  display: flex;
  align-items: center;
}
.header-mascot {
  height: 28px;
  width: auto;
}
.header-wordmark {
  margin-left: 10px;
  color: #fff;
  font-weight: 700;
  font-size: 20px;
}
.header-tagline {
  margin-left: auto;
  color: #ffcc00;
  font-style: italic;
  font-size: 12px;
}
```

Note: the mascot SVG's station-dot/wheel fills are paper-cream `#f6f4ee`, which reads
fine on the navy bar (they render as light hollows).

Update `.panel` to sit below the header bar:

```css
.panel {
  position: absolute;
  top: 64px;       /* below the header bar */
  left: 16px;
  z-index: 10;
  width: 300px;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 4px 16px rgb(0 0 0 / 0.15);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
```

Remove or update the `.panel h1` and `.tagline` CSS rules (they no longer exist in the
DOM; the lockup SVG handles them).

Adjust `.journey-card .book` background from `#111827` to `#003399` (brand navy) and
`.stop-toggle button.active` background from `#111827` to `#003399` to apply the
navy chrome consistently.

- [ ] **Step 4: Verify build + tests, commit**

```bash
cd web && npm test && npm run build && npm run lint
git add src/App.tsx src/index.css
git commit -m "feat: navy header bar with C0 lockup, branded panel chrome"
```

Expected: all tests PASS (no logic changes, only JSX/CSS). Build succeeds. The app
renders with a navy top bar containing the lockup SVG.

---

### Task 5: Self-hosted Barlow woff2 font (400/600/700)

**Files:**
- Create: `web/public/fonts/barlow-v13-latin-regular.woff2`
- Create: `web/public/fonts/barlow-v13-latin-600.woff2`
- Create: `web/public/fonts/barlow-v13-latin-700.woff2`
- Create: `web/public/fonts/barlow-v13-latin-italic.woff2`
- Modify: `web/src/index.css` (add `@font-face` rules, update `body` font-family)

**Context for the agent:** The spec requires **Barlow** (DIN 1451 rail-signage tradition)
self-hosted as woff2 — no Google Fonts runtime requests. Weights: 400 (regular),
600 (semi-bold), 700 (bold). The italic variant is needed for the gold tagline in the
lockup (though it renders inside the SVG's `<text>` element, the tagline in the header
also benefits from having the italic available system-wide).

Barlow is an open-source font (SIL Open Font License) available from
https://fonts.google.com/specimen/Barlow. The woff2 files can be downloaded from
Google Fonts' CSS API.

- [ ] **Step 1: Download the Barlow woff2 files**

```bash
mkdir -p web/public/fonts

# Fetch the CSS from Google Fonts to extract woff2 URLs, then download each file.
# The user-agent header is required to get woff2 format from Google's API.
curl -sH "User-Agent: Mozilla/5.0" \
  "https://fonts.googleapis.com/css2?family=Barlow:ital,wght@0,400;0,600;0,700;1,400&display=swap" \
  -o /tmp/barlow-css.txt

# Extract woff2 URLs and download them
grep -oP 'url\(\K[^)]+\.woff2' /tmp/barlow-css.txt | head -4

# Download each weight (inspect the CSS output for exact URLs, then):
# Regular 400:
curl -sL "$(grep -A2 'font-weight: 400' /tmp/barlow-css.txt | grep -oP 'url\(\K[^)]+\.woff2' | head -1)" \
  -o web/public/fonts/barlow-v13-latin-regular.woff2
# Semi-bold 600:
curl -sL "$(grep -A2 'font-weight: 600' /tmp/barlow-css.txt | grep -oP 'url\(\K[^)]+\.woff2' | head -1)" \
  -o web/public/fonts/barlow-v13-latin-600.woff2
# Bold 700:
curl -sL "$(grep -A2 'font-weight: 700' /tmp/barlow-css.txt | grep -oP 'url\(\K[^)]+\.woff2' | head -1)" \
  -o web/public/fonts/barlow-v13-latin-700.woff2
# Italic 400:
curl -sL "$(grep -A2 'font-style: italic' /tmp/barlow-css.txt | grep -oP 'url\(\K[^)]+\.woff2' | head -1)" \
  -o web/public/fonts/barlow-v13-latin-italic.woff2

ls -la web/public/fonts/
```

Expected: 4 woff2 files, each roughly 15–30 KB.

**IMPORTANT:** If the grep-based URL extraction doesn't work cleanly (Google's CSS
format may vary), open `/tmp/barlow-css.txt`, manually identify the 4 woff2 URLs for
latin subset, and download them individually with `curl -sL <url> -o <target>`.

- [ ] **Step 2: Add `@font-face` rules to `web/src/index.css`**

Add these rules at the top of `index.css`, immediately after the `@import "maplibre-gl/..."` line:

```css
@font-face {
  font-family: "Barlow";
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url("/fonts/barlow-v13-latin-regular.woff2") format("woff2");
}
@font-face {
  font-family: "Barlow";
  font-style: normal;
  font-weight: 600;
  font-display: swap;
  src: url("/fonts/barlow-v13-latin-600.woff2") format("woff2");
}
@font-face {
  font-family: "Barlow";
  font-style: normal;
  font-weight: 700;
  font-display: swap;
  src: url("/fonts/barlow-v13-latin-700.woff2") format("woff2");
}
@font-face {
  font-family: "Barlow";
  font-style: italic;
  font-weight: 400;
  font-display: swap;
  src: url("/fonts/barlow-v13-latin-italic.woff2") format("woff2");
}
```

Update the `body` rule from `font-family: system-ui, sans-serif;` to:
```css
body { margin: 0; font-family: "Barlow", system-ui, sans-serif; }
```

- [ ] **Step 3: Verify build + tests, commit**

```bash
cd web && npm test && npm run build && npm run lint
# Verify fonts are copied to dist:
ls -la dist/fonts/ 2>/dev/null || echo "Vite copies public/ to dist/ automatically"
git add public/fonts/ src/index.css
git commit -m "feat: self-hosted Barlow woff2 (400/600/700/italic) for rail-signage typography"
```

Expected: all tests PASS, build succeeds, lint clean. The app renders all text in Barlow.
No test delta.

---

### Task 6: Re-tune station dots / capital stars / coverage veil / dimming on paper basemap

**Files:**
- Modify: `web/src/components/Map.tsx`
- Modify: `web/src/lib/dots.ts`
- Modify: `web/src/lib/dots.test.ts`
- Modify: `web/src/lib/highlight.ts`
- Modify: `web/src/lib/highlight.test.ts`

**Context for the agent:** With the warm-paper basemap (`#F2EFE9`) and viridis-reversed
palette, the existing grey dots, grey stars, grey veil, and 0.04 dimming opacity need
contrast adjustment. The spec says "re-tune, don't redesign" — the same visual elements,
just contrast-checked against the paper background.

Current values in the code:
- `Map.tsx:52`: all-stations dot color `"#9ca3af"`, opacity `0.7`
- `Map.tsx:61`: coverage-veil fill-color `"#6b7280"`, opacity `0.08`/`0.16`
- `Map.tsx:90`: reach-dots stroke-color `"#ffffff"` (white outline)
- `Map.tsx:72`: reach-lines base width `2.5` / `1.5`
- `dots.ts:80-82`: star fill RGB `(75, 85, 99)` = `#4b5563`, rim `(255, 255, 255)`
- `highlight.ts:11`: dimmed line opacity `0.04`

**Target adjustments for warm paper:**
- All-stations dots: keep `#9ca3af` (sufficient contrast against `#F2EFE9`), but
  consider slightly darker `#8b9199` if they look too faint on the warmer background.
- Coverage veil: tint toward warm grey `"#9c9589"` (vs cool `#6b7280`) so it harmonizes
  with the paper; keep the same opacity tiers.
- Reach-dot outlines: change from `#ffffff` to `#F2EFE9` (paper color) so outlines
  blend into the basemap instead of showing a bright white ring.
- Star fill: darken to `#374151` (navy-leaning dark grey) for better authority against
  paper; white rim stays.
- Dimming opacity: raise from `0.04` to `0.08` — on the cream background, `0.04` makes
  dimmed lines almost invisible (they were tuned for white Positron). The user may want
  further tuning.

- [ ] **Step 1: Update `web/src/lib/dots.ts` star colors**

In `drawStarIcon`, change the fill color from `(75, 85, 99)` (`#4b5563`) to
`(55, 65, 81)` (`#374151`). Update the docstring: "Darker grey fill (#374151) for
authority against warm-paper basemap". The white rim `(255, 255, 255)` stays.

- [ ] **Step 2: Update `web/src/lib/dots.test.ts` star assertion**

In the test "paints a grey star center and transparent corners", change:
```typescript
    expect(img.data[at(15, 15)]).toBe(75); // dark grey fill
```
to:
```typescript
    expect(img.data[at(15, 15)]).toBe(55); // darker grey fill for paper basemap
```

- [ ] **Step 3: Update `web/src/lib/highlight.ts` dimming opacity — BOTH functions**

`highlight.ts` has TWO hardcoded 0.04 dim values that must move together (lines and
station dots must dim consistently):

1. `baseLineOpacity`: change to
```typescript
  return hasSelection ? 0.08 : 0.75;
```
2. `stationOpacityExpression` (added 2026-07-11 for journey dimming): change its
   dimmed value in the returned `["match", …]` expression from `0.04` to `0.08`.

- [ ] **Step 4: Update `web/src/lib/highlight.test.ts` dimming assertions**

Read the test file first:

```bash
grep -n "0.04" web/src/lib/highlight.test.ts
```

Update ALL matching assertions to `0.08` — this includes the `baseLineOpacity(true)`
expectation AND the `stationOpacityExpression` match-expression test whose expected
array ends with `0.04`.

- [ ] **Step 5: Update Map.tsx layer paints**

In `web/src/components/Map.tsx`, make these paint adjustments:

1. **Coverage veil** (line ~61): change `"fill-color"` from `"#6b7280"` to `"#9c9589"`.
2. **Reach-dots stroke** (line ~90): change `"circle-stroke-color"` from `"#ffffff"` to
   `"#F2EFE9"`.

Do NOT change the all-stations dot color (`#9ca3af`) or opacity (`0.7`) — leave those
for the user to judge.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd web && npm test`
Expected: all PASS (dots.test.ts updated assertion matches new fill value;
highlight.test.ts updated assertion matches new opacity).

- [ ] **Step 7: Verify build + lint, commit**

```bash
cd web && npm test && npm run build && npm run lint
git add src/components/Map.tsx src/lib/dots.ts src/lib/dots.test.ts \
        src/lib/highlight.ts src/lib/highlight.test.ts
git commit -m "feat: re-tune dot/star/veil/dimming contrast for warm-paper basemap"
```

Expected: test delta is 2 changed assertions (star fill color, dimming opacity). Build
succeeds. The user should eyeball the map with all 6 tasks landed and provide feedback
on:
- Bucket-0 yellow readability (the TUNING POINT from Task 2)
- All-stations dot visibility
- Coverage veil warmth
- Dimming level when a journey is selected

---

## Self-review notes

- Spec coverage: Phase 1 scope only — basemap-light JSON (Task 1), bucket recolor
  (Task 2), logo/lockup/favicon SVGs (Task 3), header chrome (Task 4), Barlow
  typography (Task 5), dot/star/veil/dimming re-tune (Task 6). No dark mode, no
  animations, no Phase 2/3 items.
- Task independence: each task is self-contained. Task 4 references the lockup SVG from
  Task 3, but the `<img>` tag simply shows a broken image if the file is absent — the
  build still succeeds. Task 6 references the paper color from Task 1's style, but the
  dot/veil changes are pure code values that compile regardless.
- `colors.ts` is the single source of truth for brand/data tokens (spec §Testing).
  The style JSON carries its own basemap colors (not imported from TS).
- The star `<text>★</text>` in the mascot SVG uses a Unicode character, not a font
  glyph — it renders in any browser without Barlow loaded.
- Bucket-0 yellow contrast is explicitly flagged as a user-judged tuning point in
  Task 2, per spec line 39–42.
- The `mapstyle-light.json` keeps all OpenFreeMap source/glyph/sprite URLs intact;
  only paint colors change.
