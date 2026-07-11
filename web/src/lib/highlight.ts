// Styling for backlog item J (selected-journey highlight). The thick-line treatment is
// provisional: to be revisited for an animated train once branding (item D) lands.
export type SelectedLineFilter = ["==", ["get", "id"], string];

// "" is never a station id, so a null selection matches no feature.
export function selectedLineFilter(id: string | null): SelectedLineFilter {
  return ["==", ["get", "id"], id ?? ""];
}

export function baseLineOpacity(hasSelection: boolean): number {
  return hasSelection ? 0.04 : 0.75;
}
