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
