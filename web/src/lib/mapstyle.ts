/**
 * Resolves the MapLibre style URL for the current theme.
 * Phase 1: light only. Phase 2 will add "dark" → mapstyle-dark.json.
 */
export function styleUrl(_theme: "light"): string {
  return "/mapstyle-light.json";
}
