// Single source of truth for brand and data-palette colors.
// Spec: docs/superpowers/specs/2026-07-11-branding-design.md §Color tokens.

/** Viridis-reversed data palette — validated for CVD separation (worst adjacent
 *  ΔE 24.6 deutan). Consumed by Map.tsx bucket expression and the TimeSlider
 *  gradient legend. */
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
        stationDot: "#5B7FDB",
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
