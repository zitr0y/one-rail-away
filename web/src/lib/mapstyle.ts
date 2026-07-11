import type { Theme } from "./theme";

/** Resolves the MapLibre style URL for the current theme (both forked local files). */
export function styleUrl(theme: Theme): string {
  return theme === "dark" ? "/mapstyle-dark.json" : "/mapstyle-light.json";
}
