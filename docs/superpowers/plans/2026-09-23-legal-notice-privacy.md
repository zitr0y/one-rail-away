# Legal Notice, Privacy Policy, Affiliate Label Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a legal notice and privacy policy (static pages), always-visible links to them, and an "Affiliate link" note under the Book button that appears only when affiliate links are active.

**Architecture:** Two script-free static HTML files in `web/public/` (served as-is by nginx). A tiny `GET /api/config` exposes whether `TRAINLINE_LINK_PREFIX` is set; the web client fetches it once (cached promise) and `TripDetails` shows the note when true. Header gets a "Legal" link; the map attribution gets "Legal · Privacy".

**Tech Stack:** static HTML/CSS; FastAPI + pytest; React + TypeScript + vitest.

**Spec:** `docs/superpowers/specs/2026-09-23-legal-notice-privacy-design.md` (page text is final there; this plan reproduces it as HTML).

**Commands:** Python: `uv run pytest <path> -q`, `uv run ruff check server tests`. Web (from `web/`): `npx vitest run <path>`, `npx tsc --noEmit`.

---

### Task 1: Static legal + privacy pages

**Goal:** `web/public/legal.html` and `web/public/privacy.html` with the spec's text, no JavaScript, site fonts, light/dark.

**Files:**
- Create: `web/public/legal.html`, `web/public/privacy.html`
- Test: `web/src/legalPages.test.ts`

**Acceptance Criteria:**
- [ ] Both pages contain no `<script`
- [ ] Legal page: operator name, full address, entity-encoded email + mailto, contact form link, KvK line, `id="affiliate-links"` section, link to `/privacy.html`
- [ ] Privacy page: "No cookies", server logs, OpenFreeMap, Trainline/Partnerize, rights, Autoriteit Persoonsgegevens, link to `/legal.html`
- [ ] Plain-text email `contact@onestopeurope.eu` does NOT appear literally in either file

**Verify:** `cd web && npx vitest run src/legalPages.test.ts` → pass

**Steps:**

- [ ] **Step 1: Write the failing test**

```ts
// web/src/legalPages.test.ts
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const page = (name: string) =>
  readFileSync(new URL(`../public/${name}`, import.meta.url), "utf8");

const ENCODED_EMAIL =
  "&#99;&#111;&#110;&#116;&#97;&#99;&#116;&#64;&#111;&#110;&#101;&#115;&#116;&#111;&#112;&#101;&#117;&#114;&#111;&#112;&#101;&#46;&#101;&#117;";

describe("legal pages", () => {
  for (const name of ["legal.html", "privacy.html"]) {
    it(`${name} is script-free and never spells out the email`, () => {
      const html = page(name);
      expect(html).not.toMatch(/<script/i);
      expect(html).not.toContain("contact@onestopeurope.eu");
      expect(html).toContain('href="/"');
    });
  }

  it("legal notice identifies the operator", () => {
    const html = page("legal.html");
    for (const text of ["Aaron Bussche", "Sophiaweg 76", "6523 NJ Nijmegen", "Netherlands",
      ENCODED_EMAIL, "https://aaronbussche.eu", "KvK", 'id="affiliate-links"', 'href="/privacy.html"']) {
      expect(html).toContain(text);
    }
  });

  it("privacy policy covers every processing we do", () => {
    const html = page("privacy.html");
    for (const text of ["No cookies", "IP address", "OpenFreeMap", "Trainline", "Partnerize",
      "Autoriteit Persoonsgegevens", 'href="/legal.html"']) {
      expect(html).toContain(text);
    }
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd web && npx vitest run src/legalPages.test.ts`
Expected: FAIL — `ENOENT ... legal.html`

- [ ] **Step 3: Create `web/public/legal.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Legal notice · onestopeurope</title>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<style>
@font-face { font-family: "Barlow"; font-weight: 400; font-display: swap; src: url("/fonts/barlow-v13-latin-regular.woff2") format("woff2"); }
@font-face { font-family: "Barlow"; font-weight: 700; font-display: swap; src: url("/fonts/barlow-v13-latin-700.woff2") format("woff2"); }
:root { --bg: #fff; --text: #111827; --muted: #6b7280; --link: #003399; --rule: #e5e7eb; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #0B1533; --text: #E8ECF7; --muted: #9AA6C9; --link: #ffcc00; --rule: #1A2A55; }
}
body { margin: 0; background: var(--bg); color: var(--text); font: 17px/1.55 "Barlow", system-ui, sans-serif; }
header { background: #003399; color: #fff; padding: 12px 16px; }
header a { color: #ffcc00; text-decoration: none; font-weight: 700; }
main { max-width: 40rem; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 1.8rem; margin: 0 0 16px; }
h2 { font-size: 1.15rem; margin: 28px 0 6px; }
a { color: var(--link); }
address { font-style: normal; margin: 8px 0 16px; }
.muted { color: var(--muted); }
</style>
</head>
<body>
<header><a href="/">← Back to the map</a></header>
<main>
<h1>Legal notice</h1>
<p>onestopeurope.eu is run by a private individual:</p>
<address>
Aaron Bussche<br>
Sophiaweg 76<br>
6523 NJ Nijmegen<br>
Netherlands
</address>
<p>
Email: <a href="&#109;&#97;&#105;&#108;&#116;&#111;&#58;&#99;&#111;&#110;&#116;&#97;&#99;&#116;&#64;&#111;&#110;&#101;&#115;&#116;&#111;&#112;&#101;&#117;&#114;&#111;&#112;&#101;&#46;&#101;&#117;">&#99;&#111;&#110;&#116;&#97;&#99;&#116;&#64;&#111;&#110;&#101;&#115;&#116;&#111;&#112;&#101;&#117;&#114;&#111;&#112;&#101;&#46;&#101;&#117;</a><br>
Contact form: <a href="https://aaronbussche.eu">https://aaronbussche.eu</a>
</p>
<p class="muted">Not registered with the Dutch Chamber of Commerce (KvK); no VAT number.</p>

<h2 id="affiliate-links">Affiliate links</h2>
<p>The “Search on Trainline” button may be an affiliate link: if you buy a ticket after
clicking it, Trainline may pay onestopeurope a commission. You pay the same price. It never
changes which connections the map shows or how they are ranked.</p>

<h2>Timetable data and accuracy</h2>
<p>Journeys are computed from published timetable data (credited on the map) for a sample
week. They can be incomplete or out of date — always check with the operator or seller
before you travel.</p>

<h2>Privacy</h2>
<p>See the <a href="/privacy.html">privacy policy</a>.</p>
</main>
</body>
</html>
```

- [ ] **Step 4: Create `web/public/privacy.html`** — same `<head>` (title `Privacy policy · onestopeurope`), same `<style>` block and header as legal.html, then:

```html
<main>
<h1>Privacy policy</h1>
<p class="muted">Last updated: 23 September 2026</p>

<h2>Who is responsible</h2>
<p>Aaron Bussche, address and email as in the <a href="/legal.html">legal notice</a>.</p>

<h2>No cookies, no tracking</h2>
<p>No cookies are set by onestopeurope, and it uses no analytics or advertising trackers.</p>

<h2>Server logs</h2>
<p>When you load the site, our web server records your IP address, the time, the page or
data requested, and your browser’s user agent. We use this only to run the site and keep it
secure (legitimate interest, GDPR art. 6(1)(f)). The logs are deleted automatically,
normally within a few days, and are not shared.</p>

<h2>Map tiles</h2>
<p>The map background is loaded by your browser directly from
<a href="https://openfreemap.org">OpenFreeMap</a>, which therefore receives your IP address.
OpenFreeMap’s own terms and privacy information apply to those requests.</p>

<h2>“Search on Trainline”</h2>
<p>When you click it, we log which two stations and which date were requested (no IP
address, nothing that identifies you) to count booking clicks. You are then sent to
Trainline, possibly via the affiliate network Partnerize, which may set cookies to
attribute a booking. From that point Trainline’s and Partnerize’s privacy policies apply.</p>

<h2>Your rights</h2>
<p>You can ask for access, correction, deletion or restriction, or object to processing, via
the email in the <a href="/legal.html">legal notice</a>. In practice we hold nothing that
links to you beyond short-lived server logs. You can complain to the Dutch Data Protection
Authority (<a href="https://autoriteitpersoonsgegevens.nl">Autoriteit Persoonsgegevens</a>).</p>
</main>
</body>
</html>
```

(The test looks for "No cookies" — the heading provides it.)

- [ ] **Step 5: Run to verify pass**

Run: `cd web && npx vitest run src/legalPages.test.ts`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add web/public/legal.html web/public/privacy.html web/src/legalPages.test.ts
git commit -m "feat(web): legal notice and privacy policy pages"
```

---

### Task 2: `GET /api/config`

**Goal:** Server reports whether affiliate links are active.

**Files:**
- Modify: `server/app.py` (inside `create_app`, next to the `/api/book` route)
- Test: `tests/test_server.py` (append)

**Acceptance Criteria:**
- [ ] `{"affiliate_links": false}` when `TRAINLINE_LINK_PREFIX` unset or empty
- [ ] `{"affiliate_links": true}` when set
- [ ] Response header `Cache-Control: no-cache`

**Verify:** `uv run pytest tests/test_server.py -q -k config && uv run ruff check server tests` → pass

**Steps:**

- [ ] **Step 1: Failing tests** (append to `tests/test_server.py`)

```python
def test_config_reports_affiliate_links_off(client, monkeypatch):
    monkeypatch.delenv("TRAINLINE_LINK_PREFIX", raising=False)
    resp = client.get("/api/config")
    assert resp.json() == {"affiliate_links": False}
    assert resp.headers["cache-control"] == "no-cache"


def test_config_reports_affiliate_links_on(client, monkeypatch):
    monkeypatch.setenv("TRAINLINE_LINK_PREFIX", "https://prf.hn/click/camref:ABC/destination:")
    assert client.get("/api/config").json() == {"affiliate_links": True}
```

- [ ] **Step 2: Run** `uv run pytest tests/test_server.py -q -k config` → FAIL (404)

- [ ] **Step 3: Implement** in `create_app`, right after the `/api/book` route:

```python
    @app.get("/api/config")
    def config(response: Response) -> dict:
        # Read per request so an env change needs only a container restart.
        response.headers["Cache-Control"] = "no-cache"
        return {"affiliate_links": bool(os.environ.get("TRAINLINE_LINK_PREFIX"))}
```

- [ ] **Step 4: Run** `uv run pytest tests/test_server.py -q && uv run ruff check server tests` → all pass

- [ ] **Step 5: Commit**

```bash
git add server/app.py tests/test_server.py
git commit -m "feat(server): /api/config exposes affiliate_links flag"
```

---

### Task 3: Web links + affiliate note

**Goal:** "Legal" link in the header (desktop + mobile), "Legal · Privacy" in the map attribution, and an "Affiliate link" note under the Book button when `/api/config` says so.

**Files:**
- Modify: `web/src/lib/api.ts` (add `getConfig` with cached promise + test reset)
- Modify: `web/src/components/TripDetails.tsx` (note under `a.book`, ~line 107)
- Modify: `web/src/App.tsx:184-194` (header link)
- Modify: `web/src/components/Map.tsx:102` (`customAttribution`)
- Modify: `web/src/index.css` (header link, mobile header rules ~line 385, note style near `.trip-details .book` ~line 292)
- Test: `web/src/components/TripDetails.test.tsx`, `web/src/components/Map.test.tsx`

**Acceptance Criteria:**
- [ ] `api.getConfig()` fetches `/api/config` once per session; on any error resolves `{ affiliate_links: false }`
- [ ] TripDetails renders `<a class="affiliate-note" href="/legal.html#affiliate-links">Affiliate link</a>` only when config says true
- [ ] Header shows `<a class="header-legal" href="/legal.html">Legal</a>`; on mobile it sits right-aligned before the theme toggle with a ≥44px touch target
- [ ] AttributionControl gets `customAttribution` containing `/legal.html` and `/privacy.html` links
- [ ] Existing tests still pass; tsc clean

**Verify:** `cd web && npx vitest run && npx tsc --noEmit` → all pass

**Steps:**

- [ ] **Step 1: Failing tests.** In `web/src/components/TripDetails.test.tsx` add at the top-level imports `import { api, __clearConfigCacheForTests } from "../lib/api";` and append inside `describe("TripDetails booking date", ...)`:

```tsx
  it("labels the Book button as an affiliate link when affiliate links are on", async () => {
    __clearConfigCacheForTests();
    const spy = vi.spyOn(api, "getConfig").mockResolvedValue({ affiliate_links: true });
    const container = document.createElement("div");
    const root = createRoot(container);
    await act(async () => {
      root.render(<TripDetails origin={origin} destination={destination} dest={dest}
                               maxTrains={2} stationsById={stationsById} />);
    });
    const note = container.querySelector<HTMLAnchorElement>("a.affiliate-note");
    expect(note?.getAttribute("href")).toBe("/legal.html#affiliate-links");
    expect(note?.textContent).toBe("Affiliate link");
    act(() => root.unmount());
    spy.mockRestore();
  });

  it("shows no affiliate note when affiliate links are off", async () => {
    __clearConfigCacheForTests();
    const spy = vi.spyOn(api, "getConfig").mockResolvedValue({ affiliate_links: false });
    const container = document.createElement("div");
    const root = createRoot(container);
    await act(async () => {
      root.render(<TripDetails origin={origin} destination={destination} dest={dest}
                               maxTrains={2} stationsById={stationsById} />);
    });
    expect(container.querySelector("a.affiliate-note")).toBeNull();
    act(() => root.unmount());
    spy.mockRestore();
  });
```

Note: this describe block uses `vi.useFakeTimers()` in `beforeEach`; `mockResolvedValue` promises resolve on the microtask queue, which fake timers don't block, and `await act(async ...)` flushes them. If the effect still hasn't applied, call `vi.useRealTimers()` at the start of these two tests.

In `web/src/components/Map.test.tsx`, find the existing test that asserts on `mockAttributionControl` (search `mockAttributionControl).toHaveBeenCalled`). Add (or extend it with):

```ts
    const options = mockAttributionControl.mock.calls[0][0] as { customAttribution: string };
    expect(options.customAttribution).toContain('href="/legal.html"');
    expect(options.customAttribution).toContain('href="/privacy.html"');
```

If no existing test asserts on it, add this to the first test that renders `<Map ...>` after the map is created.

- [ ] **Step 2: Run** `cd web && npx vitest run src/components/TripDetails.test.tsx src/components/Map.test.tsx` → FAIL (`getConfig` missing / no customAttribution)

- [ ] **Step 3: Implement.** `web/src/lib/api.ts` — add above `export const api`:

```ts
export interface SiteConfig { affiliate_links: boolean }

// Fetched once per session; any failure means "no affiliate label", never an error.
let configPromise: Promise<SiteConfig> | null = null;

function getConfigCached(): Promise<SiteConfig> {
  configPromise ??= get<SiteConfig>("/api/config").catch(() => ({ affiliate_links: false }));
  return configPromise;
}

/** Test-only escape hatch for the config cache. */
export function __clearConfigCacheForTests(): void {
  configPromise = null;
}
```

and add to the `api` object: `getConfig: getConfigCached,`

`web/src/components/TripDetails.tsx` — import `api` from `"../lib/api"`; inside the component add:

```tsx
  const [affiliateLinks, setAffiliateLinks] = useState(false);
  useEffect(() => {
    let live = true;
    api.getConfig().then((config) => { if (live) setAffiliateLinks(config.affiliate_links); });
    return () => { live = false; };
  }, []);
```

and directly after the closing `</a>` of the `a.book` link:

```tsx
      {affiliateLinks && (
        <a className="affiliate-note" href="/legal.html#affiliate-links">Affiliate link</a>
      )}
```

`web/src/App.tsx` header — between the tagline `<span>` and the theme-toggle `<button>`:

```tsx
        <a className="header-legal" href="/legal.html">Legal</a>
```

`web/src/components/Map.tsx:102`:

```ts
    m.addControl(new CollapsedAttributionControl({
      compact: true,
      customAttribution: '<a href="/legal.html">Legal</a> · <a href="/privacy.html">Privacy</a>',
    }));
```

`web/src/index.css` — after the `.theme-toggle:hover` rule (~line 111):

```css
.header-legal {
  margin-left: 12px; color: #fff; opacity: 0.85; font-size: 13px; text-decoration: none;
}
.header-legal:hover { opacity: 1; text-decoration: underline; }
```

after the `.trip-details .book` rule (~line 295):

```css
.trip-details .affiliate-note {
  display: block; margin-top: 4px; text-align: center; font-size: 11px;
  color: var(--text-muted); text-decoration: none;
}
.trip-details .affiliate-note:hover { text-decoration: underline; }
```

and in the mobile header rules (~line 385) replace `.mobile-layout .theme-toggle { margin-left: auto; }` with:

```css
.mobile-layout .header-legal {
  margin-left: auto; display: inline-flex; align-items: center; min-height: 44px; padding: 0 8px;
}
.mobile-layout .theme-toggle { margin-left: 0; }
```

- [ ] **Step 4: Run** `cd web && npx vitest run && npx tsc --noEmit` → all pass

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/api.ts web/src/components/TripDetails.tsx web/src/components/TripDetails.test.tsx web/src/App.tsx web/src/components/Map.tsx web/src/components/Map.test.tsx web/src/index.css
git commit -m "feat(web): Legal/Privacy links and affiliate note on Book (N)"
```

---

### Task 4: Deploy and verify (controller, after user confirms the email forward works)

**Goal:** Pages and links live on onestopeurope.eu.

**Acceptance Criteria:**
- [ ] `curl -s https://onestopeurope.eu/legal.html | grep -c "Sophiaweg"` → 1 (served the page, not the SPA)
- [ ] same for `/privacy.html` with "Autoriteit"
- [ ] `curl -s https://onestopeurope.eu/api/config` → `{"affiliate_links":false}`
- [ ] Playwright text check at 375×800: header `a.header-legal` visible; no `a.affiliate-note` after selecting a trip
- [ ] Test email to contact@onestopeurope.eu arrived (user confirms)

**Steps:**

- [ ] `git push`, then on the server `printf "y\ny\n4\n" | bash scripts/deploy.sh` (web + api rebuild, skip pipeline).
- [ ] Run the checks above (text-only, no screenshots).
