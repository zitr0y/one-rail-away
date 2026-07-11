# Branding Phase 2 — Dark Mode + Mascot Rider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship dark mode (deep-night basemap, theme toggle with `prefers-color-scheme` + persistence, per-theme overlay tokens, dark panel chrome) and the C0 mascot riding the selected journey line in a continuous animated loop. Source of truth: `docs/superpowers/specs/2026-07-12-branding-phase2-design.md`.

**Architecture:** All changes are web-side. A `theme.ts` hook resolves and persists the theme and stamps `data-theme` on `<html>`; `mapstyle-dark.json` joins the forked light style; theme switches use `map.setStyle(url, { transformStyle })` with a pure `mergeCustomStyle` helper that carries the app's five sources and six layers across the swap; theme-dependent overlay colors single-source in `themeTokens()` in `colors.ts`; panel chrome moves to CSS variables. The mascot is a DOM `maplibregl.Marker` driven by `requestAnimationFrame` over pure, unit-tested timeline helpers in `ride.ts` that share leg geometry with `linesGeoJSON` via a new `journeyLegPaths` export.

**Tech Stack:** Vite + React 19 + vitest, MapLibre GL (Marker, transformStyle), OpenFreeMap tiles.

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

### Task 1: Theme state — `theme.ts` hook + header toggle button

**Files:**
- Create: `web/src/lib/theme.ts`
- Create: `web/src/lib/theme.test.ts`
- Modify: `web/src/App.tsx` (use hook, add toggle button to header)
- Modify: `web/src/index.css` (`.theme-toggle` styles)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `type Theme = "light" | "dark"`, `parseStoredTheme(raw: string | null): Theme | null`, `resolveTheme(stored: Theme | null, systemPrefersDark: boolean): Theme`, `toggledTheme(current: Theme): Theme`, `useTheme(): [Theme, () => void]`. Task 3 imports `Theme`; Task 3's `App.tsx` change passes the hook's `theme` to `MapView`.

**Context for the agent:** Spec §Theme state: no stored choice → follow `prefers-color-scheme` (with live change listener); an explicit toggle click sticks, persisted in `localStorage` key `ose-theme`. The hook stamps `data-theme="light|dark"` on `<html>` (Task 4's CSS keys off it). The toggle button is a small sun/moon in the navy header bar, right of the tagline. Chrome stays navy `#003399` in both themes. Pure functions are unit-tested; the hook itself is thin untested glue (house pattern — the vitest environment has no DOM).

Current `App.tsx` header (lines 77–81):

```tsx
      <header className="header-bar">
        <img src="/logo-mascot-light.svg" alt="" className="header-mascot" />
        <span className="header-wordmark">onestop<span className="header-wordmark-eu">europe</span></span>
        <span className="header-tagline">nonstopeurope with onestopeurope</span>
      </header>
```

- [ ] **Step 1: Write the failing tests**

```typescript
// web/src/lib/theme.test.ts
import { describe, expect, it } from "vitest";
import { parseStoredTheme, resolveTheme, toggledTheme } from "./theme";

describe("parseStoredTheme", () => {
  it("accepts the two valid values", () => {
    expect(parseStoredTheme("light")).toBe("light");
    expect(parseStoredTheme("dark")).toBe("dark");
  });
  it("treats anything else as no stored choice", () => {
    expect(parseStoredTheme(null)).toBeNull();
    expect(parseStoredTheme("")).toBeNull();
    expect(parseStoredTheme("auto")).toBeNull();
  });
});

describe("resolveTheme", () => {
  it("explicit choice wins over the system", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
  it("no choice follows the system", () => {
    expect(resolveTheme(null, true)).toBe("dark");
    expect(resolveTheme(null, false)).toBe("light");
  });
});

describe("toggledTheme", () => {
  it("flips", () => {
    expect(toggledTheme("light")).toBe("dark");
    expect(toggledTheme("dark")).toBe("light");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npm test`
Expected: FAIL — `./theme` does not exist.

- [ ] **Step 3: Implement `web/src/lib/theme.ts`**

```typescript
// Theme state for dark mode (branding Phase 2).
// Spec: docs/superpowers/specs/2026-07-12-branding-phase2-design.md §Theme state.
import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "ose-theme";

/** Parses a raw localStorage value; anything but "light"/"dark" means "no choice yet". */
export function parseStoredTheme(raw: string | null): Theme | null {
  return raw === "light" || raw === "dark" ? raw : null;
}

/** Explicit user choice wins; otherwise follow the system. */
export function resolveTheme(stored: Theme | null, systemPrefersDark: boolean): Theme {
  return stored ?? (systemPrefersDark ? "dark" : "light");
}

export function toggledTheme(current: Theme): Theme {
  return current === "light" ? "dark" : "light";
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() =>
    resolveTheme(
      parseStoredTheme(localStorage.getItem(STORAGE_KEY)),
      window.matchMedia("(prefers-color-scheme: dark)").matches,
    ),
  );
  // Follow live system changes only while the user has made no explicit choice.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => {
      if (parseStoredTheme(localStorage.getItem(STORAGE_KEY)) === null) {
        setTheme(e.matches ? "dark" : "light");
      }
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  // Panel/chrome CSS keys off <html data-theme="...">.
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  function toggle() {
    setTheme((t) => {
      const next = toggledTheme(t);
      localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }
  return [theme, toggle];
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npm test`
Expected: all PASS.

- [ ] **Step 5: Wire the hook + toggle button into `App.tsx`**

Add the import and hook call:

```typescript
import { useTheme } from "./lib/theme";
```

Inside `App()`, after the existing `useState` block:

```typescript
  const [theme, toggleTheme] = useTheme();
```

`theme` is not passed anywhere yet (Task 3 adds the `MapView` prop) — to keep lint clean until then, reference it in the button below (it is used for the icon and the aria-label).

Replace the header with:

```tsx
      <header className="header-bar">
        <img src="/logo-mascot-light.svg" alt="" className="header-mascot" />
        <span className="header-wordmark">onestop<span className="header-wordmark-eu">europe</span></span>
        <span className="header-tagline">nonstopeurope with onestopeurope</span>
        <button className="theme-toggle" onClick={toggleTheme}
                aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}>
          {theme === "light" ? "🌙" : "☀️"}
        </button>
      </header>
```

- [ ] **Step 6: Add `.theme-toggle` styles to `web/src/index.css`**

After the `.header-tagline` rule:

```css
.theme-toggle {
  margin-left: 12px;
  border: 0;
  background: none;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  padding: 4px 6px;
  border-radius: 6px;
}
.theme-toggle:hover { background: rgb(255 255 255 / 0.12); }
```

- [ ] **Step 7: Verify build + tests, commit**

```bash
cd web && npm test && npm run build && npm run lint
git add src/lib/theme.ts src/lib/theme.test.ts src/App.tsx src/index.css
git commit -m "feat: theme state hook + header dark-mode toggle (ose-theme, prefers-color-scheme)"
```

Expected: all tests PASS (3 new test groups), build + lint clean. The button toggles `data-theme` on `<html>` (no visible change yet beyond the icon).

---

### Task 2: Fork OpenFreeMap dark style as deep-night `mapstyle-dark.json` + `styleUrl("dark")`

**Files:**
- Create: `web/public/mapstyle-dark.json`
- Modify: `web/src/lib/mapstyle.ts`
- Modify: `web/src/lib/mapstyle.test.ts`

**Interfaces:**
- Consumes: `Theme` from Task 1 (`web/src/lib/theme.ts`).
- Produces: `styleUrl(theme: Theme): string` — `"light"` → `/mapstyle-light.json`, `"dark"` → `/mapstyle-dark.json`. Task 3 calls it in `setStyle`.

**Context for the agent:** Phase 1 forked Positron into `web/public/mapstyle-light.json` (55 layers; keys `version/sources/sprite/glyphs/layers`; sources `ne2_shaded` + `openmaptiles`). Phase 2 forks OpenFreeMap's **dark** style the same way and retints to the spec tokens: land `#101C36`, water `#0A1226`. The `"sources"`, `"glyphs"`, `"sprite"` keys MUST stay exactly as fetched — they point at OpenFreeMap's servers and are required for rendering.

Current `web/src/lib/mapstyle.ts` (entire file):

```typescript
/**
 * Resolves the MapLibre style URL for the current theme.
 * Phase 1: light only. Phase 2 will add "dark" → mapstyle-dark.json.
 */
export function styleUrl(_theme: "light"): string {
  return "/mapstyle-light.json";
}
```

- [ ] **Step 1: Write the failing test**

Add to `web/src/lib/mapstyle.test.ts`:

```typescript
  it("returns the local dark style path", () => {
    expect(styleUrl("dark")).toBe("/mapstyle-dark.json");
  });
```

- [ ] **Step 2: Run tests to verify it fails**

Run: `cd web && npm test`
Expected: FAIL — `styleUrl` only accepts `"light"` (type error) / returns the light path.

- [ ] **Step 3: Update `web/src/lib/mapstyle.ts`**

Replace the entire file with:

```typescript
import type { Theme } from "./theme";

/** Resolves the MapLibre style URL for the current theme (both forked local files). */
export function styleUrl(theme: Theme): string {
  return theme === "dark" ? "/mapstyle-dark.json" : "/mapstyle-light.json";
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npm test`
Expected: all PASS (the existing `styleUrl("light")` test still passes).

- [ ] **Step 5: Fetch the OpenFreeMap dark style**

```bash
cd /home/aaron/Projects/personal/de-trains-speed-map
curl -sL https://tiles.openfreemap.org/styles/dark -o web/public/mapstyle-dark.json
wc -c web/public/mapstyle-dark.json
python3 -c "
import json
s = json.load(open('web/public/mapstyle-dark.json'))
print(list(s.keys()), len(s['layers']))
print(s['glyphs']); print(s['sprite'])
"
```

Expected: valid JSON with `sources`/`glyphs`/`sprite`/`layers`, size in the 50–400 KB range.

- [ ] **Step 6: Retint the dark style to deep night**

Read the fetched `web/public/mapstyle-dark.json`, identify layers by id/type, and apply (exact target values; leave any layer not listed as fetched):

1. **background** layer: `"background-color"` → `"#101C36"` (land-dark).
2. **Land fills** (`landcover_*`, `landuse_*`, `park`, and similar fill layers): base land value `"#101C36"`; keep parks/woods faintly distinct with `"#132340"` so they don't vanish (muted, not invisible).
3. **water** fill: `"#0A1226"`; **waterway** lines: `"#14264F"` (slightly lighter so thin lines read).
4. **Roads**: minor `"#1C2C50"`, major/highway `"#253760"` — visible but muted so the viridis palette pops.
5. **Boundaries**: `"#3D4E7C"`.
6. **Labels**: the dark style ships light label colors — keep them. If any `text-color` is dark (< mid grey), set it to `"#B9C3DE"` with `text-halo-color` `"#101C36"`.
7. **Preserve `"sources"`, `"glyphs"`, `"sprite"` exactly as fetched.**

Verification:

```bash
python3 -c "
import json
s = json.load(open('web/public/mapstyle-dark.json'))
bg = [l for l in s['layers'] if l['type'] == 'background'][0]
water = [l for l in s['layers'] if l['id'] == 'water'][0]
print(bg['paint']); print(water['paint'])
assert 'openfreemap' in s['glyphs']
"
```

Expected: background paint contains `#101C36` (case-insensitive), water contains `#0A1226`, glyphs untouched.

- [ ] **Step 7: Verify build + tests, commit**

```bash
cd web && npm test && npm run build && npm run lint
git add public/mapstyle-dark.json src/lib/mapstyle.ts src/lib/mapstyle.test.ts
git commit -m "feat: deep-night mapstyle-dark.json fork + styleUrl('dark')"
```

Expected: all tests PASS, build + lint clean. Nothing consumes the dark style yet.

---

### Task 3: `themeTokens` + `mergeCustomStyle` transform + Map.tsx theme switching

**Files:**
- Modify: `web/src/lib/colors.ts`
- Modify: `web/src/lib/colors.test.ts`
- Create: `web/src/lib/themeswap.ts`
- Create: `web/src/lib/themeswap.test.ts`
- Modify: `web/src/components/Map.tsx`
- Modify: `web/src/App.tsx` (pass `theme` to `MapView`)

**Interfaces:**
- Consumes: `Theme` (Task 1), `styleUrl` (Task 2), existing `drawStarIcon` from `web/src/lib/dots.ts`.
- Produces: `themeTokens(theme: Theme): ThemeTokens` with keys `stationDot`, `reachDotStroke`, `veil`, `riderStroke`, `riderHollow` (all hex strings) — Task 6 consumes `riderStroke`/`riderHollow`. `mergeCustomStyle(previous, next, theme)` for `transformStyle`. `MapView` gains a required `theme: Theme` prop.

**Context for the agent:** `map.setStyle()` normally wipes the app's five custom sources (`all-stations`, `reach-lines`, `reach-dots`, `coverage`, `capitals`) and six layers (`coverage-veil`, `all-stations`, `reach-lines`, `reach-lines-selected`, `reach-dots`, `capital-stars` — that is their array order in the style; `coverage-veil` was inserted before `all-stations`). MapLibre's `transformStyle` option receives `(previousStyle, nextStyle)` where `previousStyle` is the serialized CURRENT style — including GeoJSON source data and live paint values set via `setPaintProperty` — and must return the style to apply. Carrying our sources + layers through it preserves everything except **images**: `setStyle` resets the image manager, so the `star-icon` image (added in the load handler via `drawStarIcon(44)`) must be re-added, guarded by `map.hasImage`.

Theme-dependent overlay values move to a `themeTokens()` helper (spec table — dark values are STARTING POINTS for the user's calibration round):

| Token | Light (current, calibrated) | Dark (starting value) |
|---|---|---|
| stationDot | `#003399` | `#5B7FDB` (navy is invisible on `#101C36`) |
| reachDotStroke | `#F2EFE9` | `#101C36` (always the land color) |
| veil | `#9c9589` | `#6B7590` (same 0.08/0.16 opacity tiers) |
| riderStroke | `#003399` | `#F2EFE9` |
| riderHollow | `#F2EFE9` | `#101C36` |

Unchanged in both themes per spec: `BUCKET_COLORS`, gold/navy capital stars, dim opacities 0.05/0.08.

Current hardcoded values in `Map.tsx` that move to tokens: line 53 `"circle-color": "#003399"` (all-stations), line 62 `"fill-color": "#9c9589"` (coverage-veil), line 91 `"circle-stroke-color": "#F2EFE9"` (reach-dots).

- [ ] **Step 1: Write the failing tests**

Add to `web/src/lib/colors.test.ts`:

```typescript
import { themeTokens } from "./colors";

describe("themeTokens", () => {
  it("light matches today's calibrated values", () => {
    expect(themeTokens("light")).toEqual({
      stationDot: "#003399",
      reachDotStroke: "#F2EFE9",
      veil: "#9c9589",
      riderStroke: "#003399",
      riderHollow: "#F2EFE9",
    });
  });
  it("dark swaps to deep-night starting values", () => {
    expect(themeTokens("dark")).toEqual({
      stationDot: "#5B7FDB",
      reachDotStroke: "#101C36",
      veil: "#6B7590",
      riderStroke: "#F2EFE9",
      riderHollow: "#101C36",
    });
  });
});
```

(Merge the import with the existing `./colors` import line if the linter complains about duplicate imports.)

Create `web/src/lib/themeswap.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import type { StyleSpecification } from "maplibre-gl";
import { mergeCustomStyle } from "./themeswap";

function fakePrevious(): StyleSpecification {
  return {
    version: 8,
    sources: {
      openmaptiles: { type: "vector", url: "https://old-basemap" },
      "all-stations": { type: "geojson", data: { type: "FeatureCollection", features: [] } },
      "reach-lines": { type: "geojson", data: { type: "FeatureCollection", features: [] } },
      "reach-dots": { type: "geojson", data: { type: "FeatureCollection", features: [] } },
      coverage: { type: "geojson", data: { type: "FeatureCollection", features: [] } },
      capitals: { type: "geojson", data: { type: "FeatureCollection", features: [] } },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#F2EFE9" } },
      { id: "coverage-veil", type: "fill", source: "coverage",
        paint: { "fill-color": "#9c9589", "fill-opacity": 0.5 } },
      { id: "all-stations", type: "circle", source: "all-stations",
        paint: { "circle-color": "#003399", "circle-opacity": 0.25 } },
      { id: "reach-lines", type: "line", source: "reach-lines", paint: { "line-opacity": 0.05 } },
      { id: "reach-lines-selected", type: "line", source: "reach-lines", paint: {} },
      { id: "reach-dots", type: "circle", source: "reach-dots",
        paint: { "circle-stroke-color": "#F2EFE9" } },
      { id: "capital-stars", type: "symbol", source: "capitals", layout: {} },
    ],
  } as StyleSpecification;
}

function fakeNext(): StyleSpecification {
  return {
    version: 8,
    sources: { openmaptiles: { type: "vector", url: "https://new-basemap" } },
    layers: [{ id: "background", type: "background", paint: { "background-color": "#101C36" } }],
  } as StyleSpecification;
}

describe("mergeCustomStyle", () => {
  it("returns next unchanged when previous is undefined (initial load)", () => {
    const next = fakeNext();
    expect(mergeCustomStyle(undefined, next, "dark")).toBe(next);
  });

  it("carries the five custom sources; basemap sources come from next", () => {
    const merged = mergeCustomStyle(fakePrevious(), fakeNext(), "dark");
    for (const id of ["all-stations", "reach-lines", "reach-dots", "coverage", "capitals"]) {
      expect(merged.sources[id]).toBeDefined();
    }
    expect((merged.sources.openmaptiles as { url: string }).url).toBe("https://new-basemap");
  });

  it("appends the six custom layers after the basemap layers, in order", () => {
    const merged = mergeCustomStyle(fakePrevious(), fakeNext(), "dark");
    expect(merged.layers.map((l) => l.id)).toEqual([
      "background", "coverage-veil", "all-stations", "reach-lines",
      "reach-lines-selected", "reach-dots", "capital-stars",
    ]);
  });

  it("re-tints theme-dependent paints and keeps live paint state", () => {
    const merged = mergeCustomStyle(fakePrevious(), fakeNext(), "dark");
    const byId = new Map(merged.layers.map((l) => [l.id, l]));
    const stations = byId.get("all-stations") as { paint: Record<string, unknown> };
    expect(stations.paint["circle-color"]).toBe("#5B7FDB");
    expect(stations.paint["circle-opacity"]).toBe(0.25); // live value carried, not reset
    const veil = byId.get("coverage-veil") as { paint: Record<string, unknown> };
    expect(veil.paint["fill-color"]).toBe("#6B7590");
    expect(veil.paint["fill-opacity"]).toBe(0.5);
    const dots = byId.get("reach-dots") as { paint: Record<string, unknown> };
    expect(dots.paint["circle-stroke-color"]).toBe("#101C36");
  });

  it("light theme re-tints back to light values", () => {
    const merged = mergeCustomStyle(fakePrevious(), fakeNext(), "light");
    const stations = merged.layers.find((l) => l.id === "all-stations") as
      { paint: Record<string, unknown> };
    expect(stations.paint["circle-color"]).toBe("#003399");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npm test`
Expected: FAIL — `themeTokens` and `./themeswap` do not exist.

- [ ] **Step 3: Add `themeTokens` to `web/src/lib/colors.ts`**

Append to the file:

```typescript
/** Theme-dependent overlay colors — single source for Map.tsx and the mascot rider.
 *  Spec: docs/superpowers/specs/2026-07-12-branding-phase2-design.md §Per-theme overlay tokens.
 *  Light values are the user-calibrated Phase 1 result; dark values are STARTING
 *  POINTS for the user's dark calibration round. */
export interface ThemeTokens {
  stationDot: string;
  reachDotStroke: string;
  veil: string;
  riderStroke: string;
  riderHollow: string;
}

export function themeTokens(theme: "light" | "dark"): ThemeTokens {
  return theme === "dark"
    ? {
        stationDot: "#5B7FDB", // brand navy #003399 is invisible on land-dark #101C36
        reachDotStroke: "#101C36",
        veil: "#6B7590",
        riderStroke: "#F2EFE9",
        riderHollow: "#101C36",
      }
    : {
        stationDot: "#003399",
        reachDotStroke: "#F2EFE9",
        veil: "#9c9589",
        riderStroke: "#003399",
        riderHollow: "#F2EFE9",
      };
}
```

- [ ] **Step 4: Create `web/src/lib/themeswap.ts`**

```typescript
// transformStyle helper: carries the app's sources/layers across map.setStyle()
// basemap swaps. Spec: 2026-07-12-branding-phase2-design.md §Basemap dark.
import type { LayerSpecification, StyleSpecification } from "maplibre-gl";
import { themeTokens, type ThemeTokens } from "./colors";
import type { Theme } from "./theme";

export const CUSTOM_SOURCE_IDS =
  ["all-stations", "reach-lines", "reach-dots", "coverage", "capitals"] as const;

const CUSTOM_LAYER_IDS = new Set([
  "coverage-veil", "all-stations", "reach-lines",
  "reach-lines-selected", "reach-dots", "capital-stars",
]);

function withPaint(layer: LayerSpecification, extra: Record<string, unknown>): LayerSpecification {
  const paint = (layer as { paint?: Record<string, unknown> }).paint ?? {};
  return { ...layer, paint: { ...paint, ...extra } } as LayerSpecification;
}

/** Overrides only theme-dependent paint keys; everything else (live opacity
 *  expressions, filters) rides along untouched. */
function retintLayer(layer: LayerSpecification, tokens: ThemeTokens): LayerSpecification {
  if (layer.id === "all-stations") return withPaint(layer, { "circle-color": tokens.stationDot });
  if (layer.id === "coverage-veil") return withPaint(layer, { "fill-color": tokens.veil });
  if (layer.id === "reach-dots") {
    return withPaint(layer, { "circle-stroke-color": tokens.reachDotStroke });
  }
  return layer;
}

/** transformStyle hook for map.setStyle(): `previous` is the serialized CURRENT
 *  style (GeoJSON data and setPaintProperty state included), so merging from it
 *  preserves everything except images (Map.tsx re-adds star-icon). */
export function mergeCustomStyle(
  previous: StyleSpecification | undefined,
  next: StyleSpecification,
  theme: Theme,
): StyleSpecification {
  if (!previous) return next;
  const tokens = themeTokens(theme);
  const sources = { ...next.sources };
  for (const id of CUSTOM_SOURCE_IDS) {
    if (previous.sources[id]) sources[id] = previous.sources[id];
  }
  const custom = previous.layers
    .filter((l) => CUSTOM_LAYER_IDS.has(l.id))
    .map((l) => retintLayer(l, tokens));
  return { ...next, sources, layers: [...next.layers, ...custom] };
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd web && npm test`
Expected: all PASS.

- [ ] **Step 6: Wire theme into `Map.tsx`**

In `web/src/components/Map.tsx`:

1. Add imports:

```typescript
import { BUCKET_COLORS, themeTokens } from "../lib/colors";
import { mergeCustomStyle } from "../lib/themeswap";
import type { Theme } from "../lib/theme";
```

(The first line replaces the existing `import { BUCKET_COLORS } from "../lib/colors";`.)

2. Add to `Props`:

```typescript
  theme: Theme;
```

3. In the map-construction `useEffect`, replace `style: styleUrl("light"),` with:

```typescript
      style: styleUrl(props.theme),
```

(The construction effect runs once; later theme changes go through `setStyle` below. The eslint disable comment for exhaustive-deps already covers this.)

4. In the `load` handler, first line:

```typescript
      const tokens = themeTokens(propsRef.current.theme);
```

Then replace the three hardcoded paints:
- all-stations layer: `"circle-color": "#003399"` → `"circle-color": tokens.stationDot`
- coverage-veil layer: `"fill-color": "#9c9589"` → `"fill-color": tokens.veil`
- reach-dots layer: `"circle-stroke-color": "#F2EFE9"` → `"circle-stroke-color": tokens.reachDotStroke`

5. Add the theme-switch effect after the `syncHighlight` effect:

```typescript
  const appliedTheme = useRef(props.theme);
  useEffect(() => {
    const m = map.current;
    const { theme } = props;
    if (!m || appliedTheme.current === theme) return;
    appliedTheme.current = theme;
    m.setStyle(styleUrl(theme), {
      transformStyle: (prev, next) => mergeCustomStyle(prev, next, theme),
    });
    // setStyle resets the image manager; the carried capital-stars layer needs its icon back.
    m.once("styledata", () => {
      if (!m.hasImage("star-icon")) m.addImage("star-icon", drawStarIcon(44), { pixelRatio: 2 });
    });
  }, [props.theme]);
```

6. In `web/src/App.tsx`, pass the prop:

```tsx
      <MapView stations={stations} reach={reach} maxTrains={maxTrains} maxMinutes={maxMinutes}
               selectedDest={selectedDest} theme={theme}
               onSelectOrigin={selectOrigin} onSelectDestination={setSelectedDest}
               onEmptyClick={onEmptyClick} />
```

- [ ] **Step 7: Verify build + tests, commit**

```bash
cd web && npm test && npm run build && npm run lint
git add src/lib/colors.ts src/lib/colors.test.ts src/lib/themeswap.ts \
        src/lib/themeswap.test.ts src/components/Map.tsx src/App.tsx
git commit -m "feat: themeTokens + transformStyle basemap swap — dark map goes live"
```

Expected: all tests PASS. Toggling now swaps the basemap light↔dark with all overlays intact and re-tinted; a selected journey survives the swap.

---

### Task 4: Panel/chrome CSS variables + dark overrides

**Files:**
- Modify: `web/src/index.css`

**Interfaces:**
- Consumes: `data-theme` attribute stamped by Task 1's hook.
- Produces: nothing other tasks depend on.

**Context for the agent:** Spec §Panel/chrome CSS: warm-white panels → deep navy `#0B1533` with light text in dark; header bar unchanged (navy, already theme-proof); brand-navy buttons/active states stay navy in both themes (calibration point noted in a comment). This is a pure CSS task — no JS logic, so no unit test (house convention: visual verdicts are the user's; note the exception to TDD in the commit body). Every hex that represents a *surface, border, or text* color in panel/card/search/status-bar rules moves to a variable; brand navy/gold literals stay.

- [ ] **Step 1: Add the variable blocks**

In `web/src/index.css`, immediately after the `@font-face` rules and before `* { box-sizing... }`:

```css
:root {
  --surface: #fff;
  --surface-hover: #f3f4f6;
  --text: #111827;
  --text-strong: #374151;
  --text-muted: #6b7280;
  --text-subtle: #9ca3af;
  --border: #d1d5db;
  --shadow: 0 4px 16px rgb(0 0 0 / 0.15);
  --shadow-small: 0 1px 4px rgb(0 0 0 / 0.2);
}
/* Dark starting values (spec §Panel/chrome CSS) — user-calibrated later.
   Brand navy stays navy in both themes; navy-on-navy active buttons are a
   flagged calibration point. */
[data-theme="dark"] {
  --surface: #0B1533;
  --surface-hover: #1A2A55;
  --text: #E8ECF7;
  --text-strong: #C6D0EA;
  --text-muted: #9AA6C9;
  --text-subtle: #6B7590;
  --border: #2A3A66;
  --shadow: 0 4px 16px rgb(0 0 0 / 0.5);
  --shadow-small: 0 1px 4px rgb(0 0 0 / 0.6);
}
```

- [ ] **Step 2: Convert the component rules to variables**

Apply these exact replacements (the rule structure stays; only color values change):

```css
body { margin: 0; font-family: "Barlow", system-ui, sans-serif; color: var(--text); }
```

- `.panel`: `background: #fff` → `background: var(--surface)`; `box-shadow: 0 4px 16px rgb(0 0 0 / 0.15)` → `box-shadow: var(--shadow)`.
- `.search-box input`: `border: 1px solid #d1d5db` → `border: 1px solid var(--border)`; add `background: var(--surface); color: var(--text);`.
- `.search-box ul`: `background: #fff` → `background: var(--surface)`; `box-shadow: 0 4px 12px rgb(0 0 0 / 0.15)` → `box-shadow: var(--shadow)`.
- `.search-box li button`: add `color: var(--text);`.
- `.search-box li button:hover` and `.search-box li.active button`: `background: #f3f4f6` → `background: var(--surface-hover)`.
- `.search-box .country`: `color: #9ca3af` → `color: var(--text-subtle)`.
- `.stop-toggle`: `border: 1px solid #d1d5db` → `border: 1px solid var(--border)`.
- `.stop-toggle button`: `background: #fff` → `background: var(--surface)`; add `color: var(--text);`.
- `.stop-toggle button.active`: stays `background: #003399; color: #fff;` (brand navy in both themes).
- `.hint, .error`: `color: #6b7280` → `color: var(--text-muted)`.
- `.error`: stays `#dc2626` (readable on both surfaces).
- `.journey-card`: `background: #fff` → `background: var(--surface)`; shadow → `var(--shadow)`.
- `.journey-card .duration`: `color: #374151` → `color: var(--text-strong)`.
- `.journey-card .close`: add `color: var(--text);`.
- `.journey-card .action-btn`: `border: 1px solid #d1d5db` → `var(--border)`; `background: #fff` → `var(--surface)`; add `color: var(--text);`.
- `.journey-card .action-btn:hover`: `background: #f3f4f6` → `var(--surface-hover)`.
- `.journey-card .book`: stays navy/white (brand).
- `.journey-card .fineprint`: `color: #9ca3af` → `var(--text-subtle)`.
- `.status-bar`: `background: #fff` → `var(--surface)`; `box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2)` → `var(--shadow-small)`.
- `.status-bar .close`: `color: #374151` → `var(--text-strong)`.
- `.status-bar .close:hover`: `background: #f3f4f6` → `var(--surface-hover)`.
- `.header-bar`, `.header-wordmark`, `.header-tagline`, `.theme-toggle`: unchanged (navy chrome is theme-proof).

- [ ] **Step 3: Verify no stray hardcoded surface colors remain**

```bash
grep -nE '#fff|#f3f4f6|#d1d5db|#6b7280|#9ca3af|#374151|#111827' web/src/index.css
```

Expected: the ONLY hits are inside the `:root` variable block, `.stop-toggle button.active` / `.journey-card .book` (brand navy + `#fff` text, intentional), and `.header-wordmark` (`#fff` on navy, intentional).

- [ ] **Step 4: Verify build + tests, commit**

```bash
cd web && npm test && npm run build && npm run lint
git add src/index.css
git commit -m "feat: CSS-variable panel chrome with deep-navy dark overrides

CSS-only task: no unit-testable logic; dark values are calibration starting
points per spec §Panel/chrome CSS."
```

Expected: all tests PASS (no test delta), build + lint clean. Toggling now restyles panels/cards/search/status bar.

---

### Task 5: `journeyLegPaths` refactor + `ride.ts` pure timeline helpers

**Files:**
- Modify: `web/src/lib/geojson.ts`
- Modify: `web/src/lib/geojson.test.ts` (only if it exists — add `journeyLegPaths` cases to whichever file tests `linesGeoJSON`)
- Create: `web/src/lib/ride.ts`
- Create: `web/src/lib/ride.test.ts`

**Interfaces:**
- Consumes: `chaikin`, `Journey`, `Station` (existing).
- Produces:
  - `journeyLegPaths(j: Journey, stationsById: Map<string, Station>): [number, number][][]` (exported from `geojson.ts`).
  - From `ride.ts`: `TRAVERSE_MS = 7000`, `TRANSFER_PAUSE_MS = 500`, `REST_MS = 1000`; `buildRideTimeline(legPaths: [number, number][][], opts?): RideTimeline | null`; `rideStateAt(timeline: RideTimeline, tMs: number): RideState` where `RideState = { lng: number; lat: number; bearingDeg: number; moving: boolean }`; `riderTransform(bearingDeg: number): { rotateDeg: number; mirror: boolean }`. Task 6 consumes all of these.

**Context for the agent:** Spec §Geometry & timing. The mascot rides the exact geometry the selected line renders, so the per-leg chaikin(2) construction inside `linesGeoJSON` is extracted as `journeyLegPaths` and shared. Current `linesGeoJSON` body (geojson.ts lines 71–81):

```typescript
    const legCoords = j.legs.map((leg) =>
      [leg.from, ...leg.via, leg.to]
        .map((id) => stationsById.get(id))
        .filter((s): s is Station => s !== undefined)
        .map((s): [number, number] => [s.lon, s.lat]));
    // Smooth per leg so transfer corners stay sharp: a hairpin via Paris otherwise
    // rounds into a U whose apex floats over empty countryside (user report 2026-07-09).
    const coords = legCoords
      .filter((c) => c.length >= 1)
      .flatMap((c, i) => (i === 0 ? chaikin(c, 2) : chaikin(c, 2).slice(1)));
```

Timing model (spec, binding): one traverse takes `TRAVERSE_MS` split across legs **proportional to length**, `TRANSFER_PAUSE_MS` dwell between legs, `REST_MS` dwell at the destination, then loop (modulo). `TRAVERSE_MS` is the user's explicit TUNING POINT — keep the comment. Bearings are compass-style: 0 = north, 90 = east, clockwise — that is what `maplibregl.Marker.setRotation` expects with `rotationAlignment: "map"`. The rider SVG faces EAST (right): `riderTransform` returns the marker rotation plus a `mirror` flag whenever the heading has a westward component (bearing in (180, 360)), so the train never rides upside down. Mirror composition: the marker wrapper gets the rotation, an inner element gets CSS `scaleX(-1)`; a flipped (west-facing) train rotated by `bearing − 270` faces `bearing`. Distances use an equirectangular approximation with cos-latitude correction — fine at journey scale, no dependency needed.

- [ ] **Step 1: Write the failing tests**

Create `web/src/lib/ride.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import {
  buildRideTimeline, rideStateAt, riderTransform,
  TRAVERSE_MS, TRANSFER_PAUSE_MS, REST_MS,
} from "./ride";

// Two straight legs along the equator: A(0,0)→B(1,0), transfer, B(1,0)→C(4,0).
// Leg lengths 1° : 3° → move time splits 25% / 75%.
const LEGS: [number, number][][] = [
  [[0, 0], [1, 0]],
  [[1, 0], [4, 0]],
];

describe("buildRideTimeline", () => {
  it("splits TRAVERSE_MS across legs proportional to length, with pauses", () => {
    const tl = buildRideTimeline(LEGS)!;
    // move(1750) + transfer(500) + move(5250) + rest(1000)
    expect(tl.totalMs).toBe(TRAVERSE_MS + TRANSFER_PAUSE_MS + REST_MS);
    expect(tl.phases.map((p) => p.kind)).toEqual(["move", "dwell", "move", "dwell"]);
    expect(tl.phases[0].endMs - tl.phases[0].startMs).toBeCloseTo(TRAVERSE_MS * 0.25, 5);
    expect(tl.phases[2].endMs - tl.phases[2].startMs).toBeCloseTo(TRAVERSE_MS * 0.75, 5);
  });

  it("returns null for empty or zero-length paths", () => {
    expect(buildRideTimeline([])).toBeNull();
    expect(buildRideTimeline([[[2, 2], [2, 2]]])).toBeNull();
  });
});

describe("rideStateAt", () => {
  const tl = buildRideTimeline(LEGS)!;

  it("starts at the origin, moving east (bearing 90)", () => {
    const s = rideStateAt(tl, 0);
    expect(s.lng).toBeCloseTo(0, 6);
    expect(s.lat).toBeCloseTo(0, 6);
    expect(s.bearingDeg).toBeCloseTo(90, 3);
    expect(s.moving).toBe(true);
  });

  it("is halfway along leg 1 at half of leg 1's move time", () => {
    const s = rideStateAt(tl, (TRAVERSE_MS * 0.25) / 2);
    expect(s.lng).toBeCloseTo(0.5, 3);
    expect(s.moving).toBe(true);
  });

  it("pins to the transfer station during the transfer dwell", () => {
    const s = rideStateAt(tl, TRAVERSE_MS * 0.25 + TRANSFER_PAUSE_MS / 2);
    expect(s.lng).toBeCloseTo(1, 6);
    expect(s.lat).toBeCloseTo(0, 6);
    expect(s.moving).toBe(false);
  });

  it("rests at the destination at the end, then wraps around (loop)", () => {
    const atRest = rideStateAt(tl, tl.totalMs - 1);
    expect(atRest.lng).toBeCloseTo(4, 6);
    expect(atRest.moving).toBe(false);
    const wrapped = rideStateAt(tl, tl.totalMs + 5);
    expect(wrapped.lng).toBeCloseTo(rideStateAt(tl, 5).lng, 9);
  });
});

describe("riderTransform", () => {
  it("east: no rotation, no mirror", () => {
    expect(riderTransform(90)).toEqual({ rotateDeg: 0, mirror: false });
  });
  it("west: mirrored, no rotation", () => {
    expect(riderTransform(270)).toEqual({ rotateDeg: 0, mirror: true });
  });
  it("north-east climbs counterclockwise", () => {
    expect(riderTransform(45)).toEqual({ rotateDeg: -45, mirror: false });
  });
  it("south-west mirrors then climbs", () => {
    expect(riderTransform(225)).toEqual({ rotateDeg: -45, mirror: true });
  });
  it("due north/south never mirror", () => {
    expect(riderTransform(0)).toEqual({ rotateDeg: -90, mirror: false });
    expect(riderTransform(180)).toEqual({ rotateDeg: 90, mirror: false });
  });
  it("normalizes out-of-range bearings", () => {
    expect(riderTransform(450)).toEqual({ rotateDeg: 0, mirror: false }); // 450 ≡ 90
    expect(riderTransform(-90)).toEqual({ rotateDeg: 0, mirror: true }); // -90 ≡ 270
  });
});
```

Add to the file that currently tests `linesGeoJSON` (look for it with `grep -rl linesGeoJSON web/src --include='*.test.ts'`; create `web/src/lib/geojson.test.ts` additions in the same style as the existing tests there):

```typescript
import { journeyLegPaths, linesGeoJSON, chaikin } from "./geojson";

describe("journeyLegPaths", () => {
  const stations = new Map([
    ["a", { id: "a", name: "A", lat: 0, lon: 0, country: "DE", has_reach: true }],
    ["b", { id: "b", name: "B", lat: 0, lon: 1, country: "DE", has_reach: true }],
    ["c", { id: "c", name: "C", lat: 1, lon: 1, country: "DE", has_reach: true }],
  ]);
  const journey = {
    trains: 2, duration_min: 100,
    legs: [
      { train: "ICE 1", dep: "08:00", arr: "09:00", from: "a", to: "b", via: [] },
      { train: "ICE 2", dep: "09:10", arr: "10:00", from: "b", to: "c", via: [] },
    ],
  };

  it("returns one chaikin(2)-smoothed path per leg", () => {
    const paths = journeyLegPaths(journey, stations);
    expect(paths).toHaveLength(2);
    expect(paths[0]).toEqual(chaikin([[0, 0], [1, 0]], 2));
    expect(paths[1]).toEqual(chaikin([[1, 0], [1, 1]], 2));
  });

  it("is exactly the geometry linesGeoJSON renders", () => {
    const reach = {
      origin: "a", computed_at: "", sample_date: "",
      destinations: [{ id: "c", direct_per_day: 0, journeys: [journey] }],
    };
    const line = linesGeoJSON(reach, stations, 3, 1440).features[0];
    const paths = journeyLegPaths(journey, stations);
    const flattened = paths.flatMap((c, i) => (i === 0 ? c : c.slice(1)));
    expect(line.geometry.coordinates).toEqual(flattened);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npm test`
Expected: FAIL — `./ride` does not exist; `journeyLegPaths` is not exported.

- [ ] **Step 3: Extract `journeyLegPaths` in `web/src/lib/geojson.ts`**

Add above `linesGeoJSON`:

```typescript
/** Per-leg chaikin(2)-smoothed coordinate paths for a journey — shared by
 *  linesGeoJSON and the mascot rider (ride.ts) so the two can never drift.
 *  Smoothing is per leg so transfer corners stay sharp: a hairpin via Paris
 *  otherwise rounds into a U whose apex floats over empty countryside
 *  (user report 2026-07-09). */
export function journeyLegPaths(
  j: Journey, stationsById: Map<string, Station>,
): [number, number][][] {
  return j.legs
    .map((leg) =>
      [leg.from, ...leg.via, leg.to]
        .map((id) => stationsById.get(id))
        .filter((s): s is Station => s !== undefined)
        .map((s): [number, number] => [s.lon, s.lat]))
    .filter((c) => c.length >= 1)
    .map((c) => chaikin(c, 2));
}
```

Replace the `legCoords`/`coords` block inside `linesGeoJSON` with:

```typescript
    const coords = journeyLegPaths(j, stationsById)
      .flatMap((c, i) => (i === 0 ? c : c.slice(1)));
```

(The old smoothing comment moves onto `journeyLegPaths`; delete it from `linesGeoJSON`.)

- [ ] **Step 4: Create `web/src/lib/ride.ts`**

```typescript
// Mascot-rider geometry & timing: pure helpers, no MapLibre/DOM.
// Spec: docs/superpowers/specs/2026-07-12-branding-phase2-design.md §Mascot rider.

/** One full origin→destination traverse, regardless of journey length.
 *  TUNING POINT: the user is explicitly unsure about fixed duration for long
 *  and short journeys alike ("we shall find out", 2026-07-12). If fixed feels
 *  wrong on the real map, the prepared fallback is mild scaling with path
 *  length (~5–10 s clamped). Judged on the real map by the user. */
export const TRAVERSE_MS = 7000;
/** Dwell at each transfer station — reads as "changing trains". */
export const TRANSFER_PAUSE_MS = 500;
/** Rest at the destination before the loop restarts from the origin. */
export const REST_MS = 1000;

interface MovePhase {
  kind: "move";
  startMs: number;
  endMs: number;
  path: [number, number][];
  /** Cumulative km at each path vertex; cumKm[0] = 0. */
  cumKm: number[];
  totalKm: number;
}
interface DwellPhase {
  kind: "dwell";
  startMs: number;
  endMs: number;
  at: [number, number];
  /** Bearing of the segment we arrived on, so the train doesn't snap during dwells. */
  bearingDeg: number;
}
export interface RideTimeline {
  phases: (MovePhase | DwellPhase)[];
  totalMs: number;
}
export interface RideState {
  lng: number;
  lat: number;
  bearingDeg: number;
  moving: boolean;
}

/** Equirectangular distance with cos-latitude correction — plenty at journey scale. */
function segmentKm(a: [number, number], b: [number, number]): number {
  const kmPerDegLat = 111.32;
  const midLatRad = (((a[1] + b[1]) / 2) * Math.PI) / 180;
  const dx = (b[0] - a[0]) * kmPerDegLat * Math.cos(midLatRad);
  const dy = (b[1] - a[1]) * kmPerDegLat;
  return Math.hypot(dx, dy);
}

/** Compass bearing a→b: 0 = north, 90 = east, clockwise — the convention
 *  maplibregl.Marker.setRotation expects with rotationAlignment "map". */
function bearingDeg(a: [number, number], b: [number, number]): number {
  const midLatRad = (((a[1] + b[1]) / 2) * Math.PI) / 180;
  const dx = (b[0] - a[0]) * Math.cos(midLatRad);
  const dy = b[1] - a[1];
  return (Math.atan2(dx, dy) * 180) / Math.PI;
}

export interface RideOptions {
  traverseMs?: number;
  transferPauseMs?: number;
  restMs?: number;
}

/** Builds the looping phase timeline: per-leg moves (time ∝ leg length),
 *  transfer dwells between legs, one rest dwell at the destination.
 *  Returns null when there is nothing to ride (no legs / zero length). */
export function buildRideTimeline(
  legPaths: [number, number][][], opts: RideOptions = {},
): RideTimeline | null {
  const traverseMs = opts.traverseMs ?? TRAVERSE_MS;
  const transferPauseMs = opts.transferPauseMs ?? TRANSFER_PAUSE_MS;
  const restMs = opts.restMs ?? REST_MS;

  const legs = legPaths
    .filter((p) => p.length >= 2)
    .map((path) => {
      const cumKm = [0];
      for (let i = 1; i < path.length; i++) {
        cumKm.push(cumKm[i - 1] + segmentKm(path[i - 1], path[i]));
      }
      return { path, cumKm, totalKm: cumKm[cumKm.length - 1] };
    });
  const grandKm = legs.reduce((sum, l) => sum + l.totalKm, 0);
  if (legs.length === 0 || grandKm === 0) return null;

  const phases: (MovePhase | DwellPhase)[] = [];
  let t = 0;
  legs.forEach((leg, i) => {
    const moveMs = traverseMs * (leg.totalKm / grandKm);
    phases.push({ kind: "move", startMs: t, endMs: t + moveMs, ...leg });
    t += moveMs;
    const end = leg.path[leg.path.length - 1];
    const arrivalBearing = bearingDeg(leg.path[leg.path.length - 2], end);
    const dwellMs = i < legs.length - 1 ? transferPauseMs : restMs;
    phases.push({ kind: "dwell", startMs: t, endMs: t + dwellMs, at: end,
      bearingDeg: arrivalBearing });
    t += dwellMs;
  });
  return { phases, totalMs: t };
}

/** Position + heading at wall-clock offset tMs (loops via modulo). */
export function rideStateAt(timeline: RideTimeline, tMs: number): RideState {
  const t = ((tMs % timeline.totalMs) + timeline.totalMs) % timeline.totalMs;
  const phase = timeline.phases.find((p) => t >= p.startMs && t < p.endMs)
    ?? timeline.phases[timeline.phases.length - 1];
  if (phase.kind === "dwell") {
    return { lng: phase.at[0], lat: phase.at[1], bearingDeg: phase.bearingDeg, moving: false };
  }
  const f = (t - phase.startMs) / (phase.endMs - phase.startMs);
  const target = f * phase.totalKm;
  let i = 1;
  while (i < phase.cumKm.length - 1 && phase.cumKm[i] < target) i++;
  const a = phase.path[i - 1];
  const b = phase.path[i];
  const segLen = phase.cumKm[i] - phase.cumKm[i - 1];
  const g = segLen === 0 ? 0 : (target - phase.cumKm[i - 1]) / segLen;
  return {
    lng: a[0] + (b[0] - a[0]) * g,
    lat: a[1] + (b[1] - a[1]) * g,
    bearingDeg: bearingDeg(a, b),
    moving: true,
  };
}

/** The rider SVG faces east. Marker rotation is bearing−90; for westward
 *  headings we mirror horizontally (inner scaleX(-1), rotation bearing−270)
 *  so the train never rides upside down. Due north/south never mirror. */
export function riderTransform(bearing: number): { rotateDeg: number; mirror: boolean } {
  const b = ((bearing % 360) + 360) % 360;
  const mirror = b > 180;
  return { rotateDeg: mirror ? b - 270 : b - 90, mirror };
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd web && npm test`
Expected: all PASS, including every pre-existing `linesGeoJSON` test (the refactor must be behavior-identical — if any existing geometry test fails, the extraction is wrong; fix the extraction, do NOT touch the old tests).

- [ ] **Step 6: Verify build + lint, commit**

```bash
cd web && npm test && npm run build && npm run lint
git add src/lib/geojson.ts src/lib/ride.ts src/lib/ride.test.ts
# plus the geojson test file modified in Step 1
git commit -m "feat: ride.ts timeline helpers + journeyLegPaths shared with linesGeoJSON"
```

Expected: all tests PASS. Nothing visible changes yet.

---

### Task 6: Rider SVG + Marker animation wiring + highlight.ts comment

**Files:**
- Create: `web/src/lib/ridersvg.ts`
- Create: `web/src/lib/ridersvg.test.ts`
- Modify: `web/src/components/Map.tsx`
- Modify: `web/src/lib/highlight.ts` (header comment only)

**Interfaces:**
- Consumes: `journeyLegPaths` (Task 5, from `geojson.ts`), `buildRideTimeline`/`rideStateAt`/`riderTransform` (Task 5), `themeTokens` (Task 3), existing `bestJourney`.
- Produces: `riderSvg(stroke: string, hollow: string): string` — an SVG markup string for `element.innerHTML`.

**Context for the agent:** Spec §Sprite + §Wiring. The rider is the C0 train WITHOUT the baked-in route line and station dots (`web/public/logo-mascot.svg` has them; the real journey line replaces them). It is generated as a **string** (not JSX, not a public asset) so the marker element can be filled via `innerHTML` with theme colors baked in — no react-dom render, trivially testable. The viewBox is vertically symmetric about the rail line (y=80 in C0 coordinates): `32 28 132 104` puts y=80 at the exact center, so the Marker's default `anchor: "center"` sits the wheels on the polyline and rotation pivots on the rail. Gold star stays `#ffcc00` in both themes.

Transform composition (from Task 5's `riderTransform`): the OUTER marker element gets MapLibre's rotation (`setRotation`, `rotationAlignment: "map"`, `pitchAlignment: "map"`); an INNER wrapper div gets `scaleX(-1)` when mirrored. `pointer-events: none` on the outer element so the rider never steals clicks from dots (spec).

`prefers-reduced-motion: reduce` → no animation; park the mascot at the destination (`rideStateAt(timeline, timeline.totalMs - 1)` = the rest dwell).

The rider must NOT appear for journeys filtered out of view: mirror `shown()`'s cutoff by checking `journey.duration_min <= maxMinutes` (`bestJourney` already enforces `maxTrains`).

- [ ] **Step 1: Write the failing tests**

```typescript
// web/src/lib/ridersvg.test.ts
import { describe, expect, it } from "vitest";
import { riderSvg } from "./ridersvg";

describe("riderSvg", () => {
  const svg = riderSvg("#003399", "#F2EFE9");

  it("bakes in stroke and hollow colors", () => {
    expect(svg).toContain('stroke="#003399"');
    expect(svg).toContain('fill="#F2EFE9"');
  });

  it("keeps the gold star in both themes", () => {
    expect(svg).toContain('fill="#ffcc00"');
    expect(svg).toContain("★");
  });

  it("drops the baked-in route line and station dots", () => {
    expect(svg).not.toContain("M4 80"); // left line segment of the logo
    expect(svg).not.toContain('cx="14"'); // left station dot
    expect(svg).not.toContain('cx="184"'); // right station dot
  });

  it("is vertically centered on the rail (y=80) for center-anchored rotation", () => {
    expect(svg).toContain('viewBox="32 28 132 104"');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web && npm test`
Expected: FAIL — `./ridersvg` does not exist.

- [ ] **Step 3: Create `web/src/lib/ridersvg.ts`**

```typescript
// The C0 mascot as a rider: train only — the real journey line replaces the
// logo's baked-in route line and station dots. Returned as a markup string so
// the Marker element can be filled via innerHTML with theme colors baked in.
// viewBox is vertically symmetric about the rail (y=80): with the Marker's
// default center anchor, the wheels sit ON the polyline and rotation pivots
// on the rail point. Spec: 2026-07-12-branding-phase2-design.md §Sprite.
export function riderSvg(stroke: string, hollow: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="32 28 132 104" width="40">
  <path d="M38 80 V46 Q38 36 48 36 H118 Q136 36 146 50 L156 68 Q160 76 152 80 Z"
        stroke="${stroke}" stroke-width="3" fill="none" stroke-linejoin="round"/>
  <circle cx="58" cy="80" r="7" stroke="${stroke}" stroke-width="2.5" fill="${hollow}"/>
  <circle cx="126" cy="80" r="7" stroke="${stroke}" stroke-width="2.5" fill="${hollow}"/>
  <circle cx="122" cy="52" r="2.2" fill="${stroke}"/>
  <circle cx="136" cy="56" r="2.2" fill="${stroke}"/>
  <path d="M124 62 Q130 66 135 61" stroke="${stroke}" stroke-width="2" fill="none"
        stroke-linecap="round"/>
  <path d="M48 46 H100" stroke="${stroke}" stroke-width="2" stroke-dasharray="1 7"
        stroke-linecap="round"/>
  <text x="66" y="70" font-size="15" fill="#ffcc00" stroke="#eab308"
        stroke-width="0.5">★</text>
</svg>`;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web && npm test`
Expected: all PASS.

- [ ] **Step 5: Wire the rider into `Map.tsx`**

1. Add imports:

```typescript
import { destinationsGeoJSON, linesGeoJSON, bestJourney, journeyLegPaths,
  type MaxTrains } from "../lib/geojson";
import { buildRideTimeline, rideStateAt, riderTransform } from "../lib/ride";
import { riderSvg } from "../lib/ridersvg";
```

(The first line replaces the existing `../lib/geojson` import.)

2. Add the rider ref and functions inside `MapView`, after `syncHighlight`:

```typescript
  const rider = useRef<{ marker: maplibregl.Marker; raf: number } | null>(null);

  function stopRider() {
    if (!rider.current) return;
    cancelAnimationFrame(rider.current.raf);
    rider.current.marker.remove();
    rider.current = null;
  }

  function syncRider() {
    stopRider();
    const m = map.current;
    if (!m) return;
    const { reach, selectedDest, maxTrains, maxMinutes, stations, theme } = propsRef.current;
    if (!reach || !selectedDest) return;
    const dest = reach.destinations.find((d) => d.id === selectedDest);
    const journey = dest ? bestJourney(dest, maxTrains) : null;
    // Mirror shown()'s cutoff: no rider for a journey the line layer won't draw.
    if (!journey || journey.duration_min > maxMinutes) return;
    const byId = new Map(stations.map((s) => [s.id, s]));
    const timeline = buildRideTimeline(journeyLegPaths(journey, byId));
    if (!timeline) return;

    const tokens = themeTokens(theme);
    const el = document.createElement("div");
    el.style.pointerEvents = "none"; // never steal clicks from dots beneath
    const inner = document.createElement("div");
    inner.innerHTML = riderSvg(tokens.riderStroke, tokens.riderHollow);
    el.appendChild(inner);
    const marker = new maplibregl.Marker({
      element: el, rotationAlignment: "map", pitchAlignment: "map",
    });

    function apply(tMs: number) {
      const s = rideStateAt(timeline!, tMs);
      const tf = riderTransform(s.bearingDeg);
      marker.setLngLat([s.lng, s.lat]);
      marker.setRotation(tf.rotateDeg);
      inner.style.transform = tf.mirror ? "scaleX(-1)" : "";
    }

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      apply(timeline.totalMs - 1); // park at the destination, no animation
      marker.addTo(m);
      rider.current = { marker, raf: 0 };
      return;
    }
    apply(0);
    marker.addTo(m);
    const start = performance.now();
    const frame = (now: number) => {
      apply(now - start);
      if (rider.current) rider.current.raf = requestAnimationFrame(frame);
    };
    rider.current = { marker, raf: requestAnimationFrame(frame) };
  }

  useEffect(syncRider, [
    props.selectedDest, props.reach, props.maxTrains, props.maxMinutes,
    props.stations, props.theme,
  ]);
```

3. In the map-construction effect: call `syncRider();` right after the existing `syncHighlight();` in the `load` handler, and change the cleanup to stop the rider first:

```typescript
    return () => {
      stopRider();
      m.remove();
    };
```

4. If lint flags the `useEffect(syncRider, …)` missing-deps pattern, follow the file's existing convention (`syncData`/`syncHighlight` use the same shape).

- [ ] **Step 6: Resolve the provisional note in `web/src/lib/highlight.ts`**

Replace the header comment (lines 1–2):

```typescript
// Styling for backlog item J (selected-journey highlight). The thick-line treatment is
// provisional: to be revisited for an animated train once branding (item D) lands.
```

with:

```typescript
// Styling for the selected-journey highlight (backlog item J). The thick line is
// the rail the mascot rides (branding Phase 2, 2026-07-12) — no longer provisional.
```

- [ ] **Step 7: Verify build + tests, commit**

```bash
cd web && npm test && npm run build && npm run lint
git add src/lib/ridersvg.ts src/lib/ridersvg.test.ts src/components/Map.tsx src/lib/highlight.ts
git commit -m "feat: mascot rides the selected journey — looping Marker with transfer pauses"
```

Expected: all tests PASS, build + lint clean. Selecting a journey now shows the C0 train looping along the thick line, pausing at transfers, resting at the destination; it flips for westward headings, parks at the destination under reduced motion, and re-themes with the toggle.

---

## Self-review notes

- Spec coverage: theme state + toggle (Task 1), dark basemap + styleUrl (Task 2),
  transformStyle carry-over + star-icon re-add + per-theme tokens (Task 3), panel
  chrome variables (Task 4), shared leg geometry + timeline/bearing/transform helpers
  with both TUNING POINT constants (Task 5), rider sprite + Marker wiring +
  reduced-motion + highlight.ts comment resolution (Task 6). No Phase 3 items.
- Type consistency: `Theme` originates in Task 1 and is imported everywhere;
  `ThemeTokens` keys (`stationDot`, `reachDotStroke`, `veil`, `riderStroke`,
  `riderHollow`) are defined in Task 3 and consumed by name in Task 6;
  `RideTimeline`/`RideState`/`riderTransform` signatures in Task 6 match Task 5.
- The Task 5 refactor is behavior-identical by construction (`filter` before
  `chaikin`, flatten with `slice(1)` after) and locked by the
  "exactly the geometry linesGeoJSON renders" test plus all pre-existing tests.
- Marker/rAF, `setStyle`, and the `useTheme` hook are deliberately untested glue
  (house pattern); every pure function added has tests.
- CSS Task 4 is the one TDD exception, called out in its commit message.
