// Styling for backlog item J (selected-journey highlight). The thick-line treatment is
// provisional: to be revisited for an animated train once branding (item D) lands.
export type SelectedLineFilter = ["==", ["get", "id"], string];

// "" is never a station id, so a null selection matches no feature.
export function selectedLineFilter(id: string | null): SelectedLineFilter {
  return ["==", ["get", "id"], id ?? ""];
}

// Lines dim harder (0.05) than station dots (0.08): dots must stay findable as
// click targets while a journey is selected (user calibration 2026-07-11).
export function baseLineOpacity(hasSelection: boolean): number {
  return hasSelection ? 0.05 : 0.75;
}

export type StationOpacityExpression = number | ["match", ["get", "id"], string[], number, number];

export function stationOpacityExpression(
  selectedStationIds: string[] | null,
  normalOpacity: number,
  dimmedOpacity = 0.08,
): StationOpacityExpression {
  if (!selectedStationIds || selectedStationIds.length === 0) {
    return normalOpacity;
  }
  return ["match", ["get", "id"], selectedStationIds, normalOpacity, dimmedOpacity];
}

