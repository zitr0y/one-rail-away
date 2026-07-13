import type { LayerSpecification, StyleSpecification } from "maplibre-gl";
import { themeTokens, type ThemeTokens } from "./colors";
import type { Theme } from "./theme";

export const CUSTOM_SOURCE_IDS =
  ["all-stations", "reach-lines", "reach-segments", "reach-dots", "coverage", "capitals"] as const;

const CUSTOM_LAYER_IDS = new Set([
  "coverage-veil", "all-stations", "reach-lines",
  "reach-lines-selected", "reach-dots", "capital-stars",
]);

function withPaint(layer: LayerSpecification, extra: Record<string, unknown>): LayerSpecification {
  const paint = (layer as { paint?: Record<string, unknown> }).paint ?? {};
  return { ...layer, paint: { ...paint, ...extra } } as LayerSpecification;
}

function retintLayer(layer: LayerSpecification, tokens: ThemeTokens): LayerSpecification {
  if (layer.id === "all-stations") return withPaint(layer, { "circle-color": tokens.stationDot });
  if (layer.id === "coverage-veil") return withPaint(layer, { "fill-color": tokens.veil });
  if (layer.id === "reach-dots") {
    return withPaint(layer, { "circle-stroke-color": tokens.reachDotStroke });
  }
  return layer;
}

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
