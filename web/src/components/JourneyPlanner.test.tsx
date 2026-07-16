// @vitest-environment jsdom
import { useState, type ReactNode } from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import JourneyPlanner from "./JourneyPlanner";
import { buildCityLookup } from "../lib/cities";
import type { SheetState } from "../lib/mobileLayout";

vi.mock("../lib/api", () => ({
  api: { searchStations: vi.fn() },
}));

afterEach(cleanup);

const origin = { id: "A", name: "Amsterdam Centraal", lat: 52.4, lon: 4.9, country: "NL", has_reach: true };
const destination = { id: "B", name: "Paris Nord", lat: 48.9, lon: 2.4, country: "FR", has_reach: true };
const dest = {
  id: "B", direct_per_day: 2,
  journeys: [{ trains: 2, duration_min: 240, legs: [
    { train: "ICE 1", dep: "08:00", arr: "12:00", from: "A", to: "B", via: [] },
  ] }],
};
const stationsById = new Map([[origin.id, origin], [destination.id, destination]]);

interface HarnessProps {
  mobile?: boolean;
  initialSheetState?: SheetState;
  armed?: "from" | "to";
  selected?: boolean;
  header?: ReactNode;
}

function Harness({
  mobile = true,
  initialSheetState = "collapsed",
  armed = "from",
  selected = false,
  header = <div>Planner header</div>,
}: HarnessProps) {
  const [sheetState, setSheetState] = useState(initialSheetState);
  return (
    <JourneyPlanner
      reach={selected ? { origin: "A", computed_at: "", sample_date: "", destinations: [dest] } : null}
      stationsById={stationsById} cities={buildCityLookup({})} cityGroups={{}}
      origin={selected ? origin : undefined}
      destination={selected ? destination : undefined}
      dest={selected ? dest : undefined}
      maxTrains={2} maxMinutes={960} filterMinutes={Infinity} armed={armed}
      mobile={mobile} sheetState={sheetState}
      collapsedSummary={selected ? "4 h · 2 trains" : null}
      header={header} onSheetStateChange={setSheetState}
      onSetOrigin={vi.fn()} onClearOrigin={vi.fn()} onSetDest={vi.fn()}
      onClearDest={vi.fn()} onSwap={vi.fn()} onArm={vi.fn()}
      onMaxTrains={vi.fn()} onMaxMinutes={vi.fn()}
    />
  );
}

describe("JourneyPlanner mobile sheet", () => {
  it("starts_collapsed_on_mobile_and_toggles_open_and_closed_by_handle_tap", () => {
    render(<Harness />);
    const handle = screen.getByRole("button", { name: "Expand journey planner" });
    expect(handle.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(handle);
    expect(screen.getByRole("button", { name: "Collapse journey planner" }).getAttribute("aria-expanded")).toBe("true");
    expect(document.querySelector(".panel")?.classList.contains("sheet-expanded")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Collapse journey planner" }));
    expect(screen.getByRole("button", { name: "Expand journey planner" }).getAttribute("aria-expanded")).toBe("false");
  });

  it("opens_on_upward_swipe_and_collapses_on_downward_swipe", () => {
    render(<Harness />);
    const handle = screen.getByRole("button", { name: "Expand journey planner" });
    fireEvent.pointerDown(handle, { clientY: 200 });
    fireEvent.pointerUp(handle, { clientY: 150 });
    expect(screen.getByRole("button", { name: "Collapse journey planner" }).getAttribute("aria-expanded")).toBe("true");
    fireEvent.pointerDown(screen.getByRole("button", { name: "Collapse journey planner" }), { clientY: 150 });
    fireEvent.pointerUp(screen.getByRole("button", { name: "Collapse journey planner" }), { clientY: 200 });
    expect(screen.getByRole("button", { name: "Expand journey planner" }).getAttribute("aria-expanded")).toBe("false");
  });

  it("collapsed_bar_shows_only_the_active_origin_chooser_before_an_origin_exists", () => {
    render(<Harness armed="from" />);
    expect(screen.getByPlaceholderText("Start from…")).toBeTruthy();
    expect(screen.getByPlaceholderText("To… (or click the map)")
      .closest<HTMLElement>(".station-field")?.hidden).toBe(true);
    expect(screen.queryByRole("group", { name: "Maximum trains" })).toBeNull();
    expect(screen.queryByRole("slider")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Amsterdam Centraal → Paris Nord" })).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("collapsed_bar_shows_the_active_destination_chooser_and_one_journey_summary", () => {
    render(<Harness armed="to" selected />);
    expect(screen.queryByRole("button", { name: "Amsterdam Centraal" })).toBeNull();
    expect(screen.getByRole("button", { name: "Paris Nord" })).toBeTruthy();
    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(screen.getByRole("status").textContent).toContain("4 h · 2 trains");
  });

  it("collapsed_bar_keeps_one_summary_when_the_origin_chooser_is_rearmed", () => {
    render(<Harness armed="from" selected />);
    expect(screen.getByRole("button", { name: "Amsterdam Centraal" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Paris Nord" })).toBeNull();
    expect(screen.getAllByRole("status")).toHaveLength(1);
  });

  it("expanded_sheet_reveals_the_existing_header_selector_slider_and_trip_details_in_order", () => {
    render(<Harness initialSheetState="expanded" selected />);
    const header = screen.getByText("Planner header");
    const from = screen.getByRole("button", { name: "Amsterdam Centraal" });
    const to = screen.getByRole("button", { name: "Paris Nord" });
    const selector = screen.getByRole("group", { name: "Maximum trains" });
    const slider = screen.getByText("Max travel time:").closest("label")!;
    const heading = screen.getByRole("heading", { name: "Amsterdam Centraal → Paris Nord" });
    expect(within(document.body).getByRole("button", { name: "Collapse journey planner" })).toBeTruthy();
    expect(header.compareDocumentPosition(from) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(from.compareDocumentPosition(to) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(to.compareDocumentPosition(selector) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(selector.compareDocumentPosition(slider) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(slider.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("desktop_mode_hides_the_sheet_handle_and_keeps_all_existing_panel_controls_available", () => {
    render(<Harness mobile={false} initialSheetState="collapsed" selected />);
    expect(screen.queryByRole("button", { name: /journey planner/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Amsterdam Centraal" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Paris Nord" })).toBeTruthy();
    expect(screen.getByRole("group", { name: "Maximum trains" })).toBeTruthy();
    expect(screen.getByText("Max travel time:")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Amsterdam Centraal → Paris Nord" })).toBeTruthy();
  });
});
