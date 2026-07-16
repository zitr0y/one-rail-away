import { useEffect, useState } from "react";
import { bestJourney, type MaxTrains } from "./geojson";
import type { Destination } from "./types";

export type SheetState = "collapsed" | "expanded";

export const MOBILE_MAX_WIDTH = 768;
export const COARSE_SMALL_MAX_WIDTH = 1024;
export const COLLAPSED_SHEET_PX = 112;
export const COLLAPSED_SHEET_WITH_CONTEXT_PX = 136;
export const EXPANDED_SHEET_VIEWPORT_FRACTION = 0.88;

const SWIPE_THRESHOLD_PX = 32;

export function isMobileLayout(width: number, coarsePointer: boolean): boolean {
  return width <= MOBILE_MAX_WIDTH || (coarsePointer && width <= COARSE_SMALL_MAX_WIDTH);
}

export function appLayoutClassName(
  mobile: boolean,
  state: SheetState,
  hasContext: boolean,
): string {
  if (!mobile) return "app";

  const classes = ["app", "mobile-layout", `sheet-${state}`];
  if (state === "collapsed" && hasContext) classes.push("sheet-has-context");
  return classes.join(" ");
}

export function sheetStateAfterGesture(
  current: SheetState,
  startY: number,
  endY: number,
): SheetState {
  if (endY <= startY - SWIPE_THRESHOLD_PX) return "expanded";
  if (endY >= startY + SWIPE_THRESHOLD_PX) return "collapsed";
  return current === "collapsed" ? "expanded" : "collapsed";
}

export function collapsedJourneySummary(
  dest: Destination | undefined,
  maxTrains: MaxTrains,
): string | null {
  if (!dest) return null;

  const journey = bestJourney(dest, maxTrains);
  if (!journey) return null;

  const hours = Math.floor(journey.duration_min / 60);
  const minutes = journey.duration_min % 60;
  const duration = `${hours} h${minutes ? ` ${minutes} min` : ""}`;
  const connections = journey.trains === 1 ? "nonstop" : `${journey.trains} trains`;
  return `${duration} · ${connections}`;
}

export function sheetBottomInsetPx(
  viewportHeight: number,
  state: SheetState,
  hasContext: boolean,
): number {
  if (state === "expanded") return Math.round(viewportHeight * EXPANDED_SHEET_VIEWPORT_FRACTION);
  return hasContext ? COLLAPSED_SHEET_WITH_CONTEXT_PX : COLLAPSED_SHEET_PX;
}

export function useMobileLayout(): boolean {
  const [mobile, setMobile] = useState(() => {
    const pointerQuery = window.matchMedia("(pointer: coarse)");
    return isMobileLayout(window.innerWidth, pointerQuery.matches);
  });

  useEffect(() => {
    const pointerQuery = window.matchMedia("(pointer: coarse)");
    const updateLayout = () => {
      setMobile(isMobileLayout(window.innerWidth, pointerQuery.matches));
    };

    window.addEventListener("resize", updateLayout);
    pointerQuery.addEventListener("change", updateLayout);
    return () => {
      window.removeEventListener("resize", updateLayout);
      pointerQuery.removeEventListener("change", updateLayout);
    };
  }, []);

  return mobile;
}
