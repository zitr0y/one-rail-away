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
