# About Dialog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "?" header button opens an About dialog (mission, how to read, data sources in use + wanted, legal links), replacing the header "Legal" link.

**Architecture:** New `AboutDialog` component (controlled by App state) + a plain-data `aboutContent.ts`. App owns `aboutOpen`, the `?` button ref (focus return) and suppresses its global Escape handler while the dialog is open.

**Tech Stack:** React + TypeScript, vitest + jsdom, plain CSS in `web/src/index.css`.

**Spec:** `docs/superpowers/specs/2026-09-23-about-dialog-design.md`

**Commands (from `web/`):** `npx vitest run <path>`, `npm run build` (MUST pass — it type-checks tests too; don't use `node:fs` in tests).

---

### Task 1: AboutDialog component + content

**Goal:** Self-contained dialog component with the approved content and a11y behaviour.

**Files:**
- Create: `web/src/components/aboutContent.ts`, `web/src/components/AboutDialog.tsx`
- Modify: `web/src/index.css` (append dialog styles)
- Test: `web/src/components/AboutDialog.test.tsx`

**Acceptance Criteria:**
- [ ] Renders `role="dialog"`, `aria-modal="true"`, labelled by its `<h2>` "About onestopeurope"
- [ ] Headings "Why this map exists", "How to read it", "Data"
- [ ] Lists every in-use operator and every wanted country/operator from `aboutContent.ts`
- [ ] Links: `/legal.html`, `/privacy.html`, the GitHub data-sources URL
- [ ] × button focused on mount; × / Escape / backdrop click call `onClose`; clicks inside the panel don't

**Verify:** `cd web && npx vitest run src/components/AboutDialog.test.tsx` → pass

**Steps:**

- [ ] **Step 1: Failing test**

```tsx
// web/src/components/AboutDialog.test.tsx
// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AboutDialog from "./AboutDialog";
import { IN_USE, WANTED_COUNTRIES, WANTED_OPERATORS, DATA_SOURCES_URL } from "./aboutContent";

let container: HTMLDivElement;
let root: Root;
let onClose: ReturnType<typeof vi.fn>;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  onClose = vi.fn();
  act(() => root.render(<AboutDialog onClose={onClose} />));
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

describe("AboutDialog", () => {
  it("is a labelled modal dialog with the three sections", () => {
    const dialog = container.querySelector<HTMLElement>('[role="dialog"]')!;
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    const title = document.getElementById(dialog.getAttribute("aria-labelledby")!)!;
    expect(title.textContent).toBe("About onestopeurope");
    const headings = [...dialog.querySelectorAll("h3")].map((h) => h.textContent);
    expect(headings).toEqual(["Why this map exists", "How to read it", "Data"]);
  });

  it("lists data in use and wanted, and links legal pages", () => {
    const text = container.textContent!;
    for (const s of IN_USE) expect(text).toContain(s.operator);
    for (const c of WANTED_COUNTRIES) expect(text).toContain(c);
    for (const o of WANTED_OPERATORS) expect(text).toContain(o.operator);
    const hrefs = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual(expect.arrayContaining(["/legal.html", "/privacy.html", DATA_SOURCES_URL]));
  });

  it("focuses the close button on open", () => {
    expect(document.activeElement?.getAttribute("aria-label")).toBe("Close");
  });

  it("closes on the close button, Escape and backdrop, not on panel clicks", () => {
    act(() => container.querySelector<HTMLButtonElement>('[aria-label="Close"]')!.click());
    expect(onClose).toHaveBeenCalledTimes(1);
    act(() => { window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })); });
    expect(onClose).toHaveBeenCalledTimes(2);
    act(() => container.querySelector<HTMLElement>(".about-backdrop")!.click());
    expect(onClose).toHaveBeenCalledTimes(3);
    act(() => container.querySelector<HTMLElement>(".about-panel")!.click());
    expect(onClose).toHaveBeenCalledTimes(3);
  });
});
```

- [ ] **Step 2: Run** `cd web && npx vitest run src/components/AboutDialog.test.tsx` → FAIL (module not found)

- [ ] **Step 3: Implement `aboutContent.ts`**

```ts
// Hand-kept in sync with docs/data-sources.md (backlog BA).
export const DATA_SOURCES_URL =
  "https://github.com/zitr0y/one-rail-away/blob/main/docs/data-sources.md";

export const IN_USE: { operator: string; country: string }[] = [
  { operator: "DB", country: "Germany" },
  { operator: "FlixTrain", country: "Germany" },
  { operator: "SNCF", country: "France" },
  { operator: "ÖBB", country: "Austria" },
  { operator: "SBB", country: "Switzerland" },
  { operator: "NS", country: "Netherlands" },
  { operator: "Rejseplanen", country: "Denmark" },
  { operator: "CP", country: "Portugal" },
  { operator: "Trenitalia", country: "Italy" },
  { operator: "Renfe", country: "Spain" },
  { operator: "PKP", country: "Poland" },
];

export const WANTED_COUNTRIES: string[] = [
  "Czechia", "Slovakia", "Hungary", "Slovenia", "Croatia", "Belgium",
  "Luxembourg", "Great Britain", "Ukraine", "Romania", "Lithuania",
];

export const WANTED_OPERATORS: { operator: string; where: string }[] = [
  { operator: "Italo", where: "Italy" },
  { operator: "Ouigo España", where: "Spain" },
  { operator: "iryo", where: "Spain" },
  { operator: "WESTbahn", where: "Austria" },
  { operator: "RegioJet", where: "Czechia/Slovakia" },
  { operator: "Leo Express", where: "Czechia/Slovakia" },
];
```

- [ ] **Step 4: Implement `AboutDialog.tsx`**

```tsx
import { useEffect, useId, useRef } from "react";
import { DATA_SOURCES_URL, IN_USE, WANTED_COUNTRIES, WANTED_OPERATORS } from "./aboutContent";

interface Props { onClose: () => void }

export default function AboutDialog({ onClose }: Props) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="about-backdrop" onClick={onClose}>
      <div className="about-panel" role="dialog" aria-modal="true" aria-labelledby={titleId}
           onClick={(e) => e.stopPropagation()}>
        <div className="about-head">
          <h2 id={titleId}>About onestopeurope</h2>
          <button ref={closeRef} type="button" className="about-close" aria-label="Close"
                  onClick={onClose}>×</button>
        </div>

        <h3>Why this map exists</h3>
        <p>Flying is often the default for trips in Europe, mostly because it’s hard to see
          what’s possible by train. onestopeurope shows, from any station, everywhere you can
          reach by train — and how many changes it takes. It starts with <strong>nonstop</strong>{" "}
          trains, because a journey without changes is the one people actually enjoy taking.</p>

        <h3>How to read it</h3>
        <p>Pick a station. Colours show travel time; lines show the routes. Switch between{" "}
          <strong>Nonstop</strong>, <strong>One stop</strong> and <strong>Two stops</strong> to
          allow changes. Tap a destination for example trains, how often they run, and a link
          to book.</p>

        <h3>Data</h3>
        <p><strong>Timetables from:</strong>{" "}
          {IN_USE.map((s) => `${s.operator} (${s.country})`).join(", ")}.</p>
        <p><strong>Not covered yet.</strong> No feed of their own: {WANTED_COUNTRIES.join(", ")}{" "}
          — trains <em>into</em> them show up, journeys <em>from</em> them don’t. Missing
          operators: {WANTED_OPERATORS.map((o) => `${o.operator} (${o.where})`).join(", ")}.</p>
        <p>Know an open timetable feed for one of these?{" "}
          <a href="/legal.html">Get in touch</a>. Full, current list:{" "}
          <a href={DATA_SOURCES_URL} target="_blank" rel="noopener noreferrer">data sources</a>.</p>

        <p className="about-foot">
          <a href="/legal.html">Legal notice</a> · <a href="/privacy.html">Privacy</a> ·
          Built by Aaron Bussche as a free side project.
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Append CSS to `web/src/index.css`** (use existing tokens `--surface`, `--text`, `--text-muted`; header is `#003399`, z-index 20)

```css
/* About dialog (backlog BA). */
.about-backdrop {
  position: fixed; inset: 0; z-index: 40; background: rgb(0 0 0 / 0.45);
  display: flex; align-items: center; justify-content: center; padding: 16px;
}
.about-panel {
  background: var(--surface); color: var(--text); border-radius: 12px;
  max-width: 36rem; width: 100%; max-height: calc(100vh - 32px); overflow-y: auto;
  padding: 20px 22px; box-shadow: 0 12px 40px rgb(0 0 0 / 0.3); font-size: 15px; line-height: 1.5;
}
.about-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.about-panel h2 { margin: 0; font-size: 20px; }
.about-panel h3 { margin: 18px 0 4px; font-size: 15px; }
.about-panel p { margin: 0 0 8px; }
.about-panel a { color: inherit; }
.about-close {
  border: 0; background: none; color: var(--text-muted); font-size: 24px; line-height: 1;
  cursor: pointer; padding: 4px 8px; border-radius: 6px; min-width: 44px; min-height: 44px;
}
.about-close:hover { background: var(--surface-hover); }
.about-foot { margin-top: 16px !important; color: var(--text-muted); font-size: 13px; }
.mobile-layout .about-backdrop { align-items: flex-start; padding: 48px 0 0; }
.mobile-layout .about-panel {
  border-radius: 12px 12px 0 0; max-width: none; max-height: calc(100vh - 48px);
}
```

(The mobile rules apply because App renders the dialog inside the `.mobile-layout` root div.)

- [ ] **Step 6: Run** `cd web && npx vitest run src/components/AboutDialog.test.tsx` → 4 passed

- [ ] **Step 7: Commit**

```bash
git add web/src/components/aboutContent.ts web/src/components/AboutDialog.tsx web/src/components/AboutDialog.test.tsx web/src/index.css
git commit -m "feat(web): About dialog with mission, data sources and legal links (BA)"
```

---

### Task 2: Wire "?" into the header; remove "Legal" link

**Goal:** App opens/closes the dialog, returns focus, and keeps Escape from clearing the selection while open.

**Files:**
- Modify: `web/src/App.tsx` (state near line 28; Escape effect ~line 164-175; header ~line 184-194; render dialog at the end of the root div)
- Modify: `web/src/index.css` (remove `.header-legal` rules incl. the mobile one; add `.about-toggle`)
- Test: `web/src/App.test.tsx` if it exists, otherwise create `web/src/components/AboutWiring.test.tsx`

**Acceptance Criteria:**
- [ ] Header has `button.about-toggle` (`aria-label="About & legal"`, `title="About & legal"`, `aria-haspopup="dialog"`, text `?`) before the theme toggle; no `a.header-legal`
- [ ] Click opens the dialog; closing returns focus to the `?` button
- [ ] While open, App's global Escape handler returns early (selection untouched)
- [ ] `npm run build` passes

**Verify:** `cd web && npx vitest run && npm run build` → pass

**Steps:**

- [ ] **Step 1: Test.** Check whether `web/src/App.test.tsx` exists (`ls web/src/App.test.tsx`). If it does, add tests there following its existing render/mocking setup. If not, mounting the whole App (MapLibre, fetches) is heavy — instead test the wiring via a narrow render: mount `<App />` only if an existing test already does so with mocks you can copy; otherwise skip an App-level test and rely on AboutDialog tests plus the Step 4 build and the manual check in Task 3. Minimum required assertion wherever App is rendered: `container.querySelector("a.header-legal") === null` and clicking `button.about-toggle` renders `[role="dialog"]`, and after pressing × `document.activeElement` is the `?` button.

- [ ] **Step 2: Implement in `App.tsx`.** Add import `import AboutDialog from "./components/AboutDialog";`. With the other state:

```tsx
  const [aboutOpen, setAboutOpen] = useState(false);
  const aboutButtonRef = useRef<HTMLButtonElement>(null);
  const closeAbout = useCallback(() => {
    setAboutOpen(false);
    aboutButtonRef.current?.focus();
  }, []);
```

In the global Escape `useEffect`, add as the first line inside `onKeyDown` after the key check:

```tsx
      if (aboutOpen) return; // the About dialog handles its own Escape
```

and add `aboutOpen` to that effect's dependency array.

In the header, replace `<a className="header-legal" href="/legal.html">Legal</a>` with:

```tsx
        <button ref={aboutButtonRef} type="button" className="about-toggle"
                aria-label="About & legal" title="About & legal" aria-haspopup="dialog"
                onClick={() => setAboutOpen(true)}>?</button>
```

Just before the root `</div>` closes, add:

```tsx
      {aboutOpen && <AboutDialog onClose={closeAbout} />}
```

- [ ] **Step 3: CSS.** Remove the `.header-legal` and `.header-legal:hover` rules and the `.mobile-layout .header-legal` rule. Add after `.theme-toggle:hover`:

```css
.about-toggle {
  margin-left: 12px; border: 0; background: none; cursor: pointer; color: #fff;
  font: 700 16px/1 "Barlow", system-ui, sans-serif; padding: 4px 8px; border-radius: 6px;
}
.about-toggle:hover { background: rgb(255 255 255 / 0.12); }
```

In the mobile header rules, replace the `.mobile-layout .header-legal {...}` block with:

```css
.mobile-layout .about-toggle { margin-left: auto; min-width: 44px; min-height: 44px; }
```

(keep `.mobile-layout .theme-toggle { margin-left: 0; }`).

- [ ] **Step 4: Run** `cd web && npx vitest run && npm run build` → all pass

- [ ] **Step 5: Commit**

```bash
git add web/src/App.tsx web/src/index.css web/src/App.test.tsx
git commit -m "feat(web): ? button opens About dialog; drop header Legal link (BA)"
```

(Add `AboutWiring.test.tsx` instead of `App.test.tsx` if that's the file you created.)

---

### Task 3: Deploy + verify (controller)

- [ ] `git push`; server: `printf "y\nn\n4\n" | bash scripts/deploy.sh` (web only).
- [ ] Playwright text checks at 375×800 and 1280×800: `button.about-toggle` visible and not covered; click → dialog visible, contains "Legal notice"; Escape closes; `a.header-legal` absent.
- [ ] Mark BA shipped in `docs/superpowers/feedback-backlog.md`.
