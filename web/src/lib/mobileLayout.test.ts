import { describe, expect, it } from "vitest";
import type { Destination } from "./types";
import {
  appLayoutClassName,
  collapsedJourneySummary,
  isMobileLayout,
  sheetBottomInsetPx,
  sheetStateAfterGesture,
  type SheetState,
} from "./mobileLayout";

function destination(duration_min: number, trains: number): Destination {
  return {
    id: "destination",
    direct_per_day: 0,
    journeys: [{ duration_min, trains, legs: [] }],
  };
}

describe("mobile layout contracts", () => {
  it("uses_mobile_layout_at_768_pixels_and_below", () => {
    for (const width of [320, 767, 768]) {
      expect(isMobileLayout(width, false)).toBe(true);
    }
  });

  it("keeps_fine_pointer_layout_desktop_above_768_pixels", () => {
    expect(isMobileLayout(769, false)).toBe(false);
    expect(isMobileLayout(1024, false)).toBe(false);
  });

  it("uses_mobile_layout_for_a_coarse_pointer_up_to_1024_pixels", () => {
    expect(isMobileLayout(769, true)).toBe(true);
    expect(isMobileLayout(1024, true)).toBe(true);
  });

  it("keeps_coarse_pointer_layout_desktop_above_1024_pixels", () => {
    expect(isMobileLayout(1025, true)).toBe(false);
  });

  it("returns_breakpoint_and_sheet_state_classes_without_altering_desktop_class", () => {
    expect(appLayoutClassName(false, "collapsed", false)).toBe("app");
    expect(appLayoutClassName(false, "expanded", true)).toBe("app");
    expect(appLayoutClassName(true, "collapsed", false)).toBe(
      "app mobile-layout sheet-collapsed",
    );
    expect(appLayoutClassName(true, "expanded", false)).toBe(
      "app mobile-layout sheet-expanded",
    );
    expect(appLayoutClassName(true, "collapsed", true)).toBe(
      "app mobile-layout sheet-collapsed sheet-has-context",
    );
  });

  it("maps_handle_taps_and_vertical_swipes_to_the_two_sheet_states", () => {
    expect(sheetStateAfterGesture("collapsed", 200, 200)).toBe("expanded");
    expect(sheetStateAfterGesture("collapsed", 200, 168)).toBe("expanded");
    expect(sheetStateAfterGesture("expanded", 168, 200)).toBe("collapsed");
  });

  it("ignores_horizontal_or_subthreshold_drag_direction_as_a_new_snap_state", () => {
    expect(sheetStateAfterGesture("collapsed", 200, 169)).toBe("expanded");

    const states: SheetState[] = ["collapsed", "expanded"];
    for (const current of states) {
      for (const [startY, endY] of [[200, 200], [200, 169], [200, 168], [200, 232]]) {
        expect(states).toContain(sheetStateAfterGesture(current, startY, endY));
      }
    }
  });

  it("formats_zero_or_one_collapsed_journey_context_line", () => {
    expect(collapsedJourneySummary(undefined, 2)).toBeNull();
    expect(collapsedJourneySummary(destination(240, 2), 1)).toBeNull();
    expect(collapsedJourneySummary(destination(240, 2), 2)).toBe("4 h · 2 trains");
    expect(collapsedJourneySummary(destination(125, 1), 1)).toBe("2 h 5 min · nonstop");
  });

  it("computes_sheet_bottom_insets_for_collapsed_context_and_expanded_states", () => {
    expect(sheetBottomInsetPx(800, "collapsed", false)).toBe(92);
    expect(sheetBottomInsetPx(800, "collapsed", true)).toBe(100);
    expect(sheetBottomInsetPx(800, "expanded", false)).toBe(704);
  });
});
