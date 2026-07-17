// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import FrequencyHeatStrip, { histogramRows } from "./FrequencyHeatStrip";

afterEach(cleanup);

const bins = (fill: Record<number, number> = {}): number[] =>
  Array.from({ length: 24 }, (_, hour) => fill[hour] ?? 0);

describe("histogramRows", () => {
  it("buckets 24 hour bins into morning/afternoon/evening per sorted date", () => {
    const rows = histogramRows({
      "2026-07-21": bins({ 6: 2, 13: 1, 20: 3 }), // a Tuesday
      "2026-07-20": bins({ 0: 1, 11: 1 }),        // a Monday
    })!;
    expect(rows.map((row) => row.weekday)).toEqual(["Mon", "Tue"]);
    expect(rows[0].dayparts).toEqual([2, 0, 0]);
    expect(rows[1].dayparts).toEqual([2, 1, 3]);
  });

  it("rejects missing, empty, wrong-length, and negative histograms", () => {
    expect(histogramRows(undefined)).toBeNull();
    expect(histogramRows({})).toBeNull();
    expect(histogramRows({ "2026-07-20": [1, 2, 3] })).toBeNull();
    expect(histogramRows({ "2026-07-20": bins({ 5: -1 }) })).toBeNull();
  });
});

describe("FrequencyHeatStrip", () => {
  const rows = histogramRows({
    "2026-07-20": bins({ 8: 4 }),
    "2026-07-21": bins({ 8: 1, 14: 2 }),
  })!;

  const renderStrip = (onToggle = vi.fn()) =>
    render(<FrequencyHeatStrip rows={rows} expanded={false} legsId="legs" onToggle={onToggle} />);

  it("renders days as column headers and dayparts as icon-labelled rows", () => {
    const { container } = renderStrip();
    const days = [...container.querySelectorAll(".frequency-heat-day")].map((el) => el.textContent);
    expect(days).toEqual(["Mon", "Tue"]);
    const labels = [...container.querySelectorAll(".frequency-heat-daypart")];
    expect(labels).toHaveLength(3);
    expect(labels.map((el) => el.getAttribute("title"))).toEqual(["Morning", "Afternoon", "Evening"]);
    expect(labels.every((el) => el.querySelector("svg.frequency-daypart-icon"))).toBe(true);
    expect([...container.querySelectorAll(".frequency-daypart-word")].map((el) => el.textContent))
      .toEqual(["Morning", "Afternoon", "Evening"]);
    expect(container.querySelectorAll(".frequency-heat-cell")).toHaveLength(6);
  });

  it("assigns levels relative to the busiest daypart and titles every cell", () => {
    const { container } = renderStrip();
    const cells = [...container.querySelectorAll(".frequency-heat-cell")];
    // Row-major by daypart: Mon/Tue morning, Mon/Tue afternoon, Mon/Tue evening.
    expect(cells[0].className).toContain("frequency-heat-level-4"); // 4 of max 4
    expect(cells[1].className).toContain("frequency-heat-level-1"); // 1 of max 4
    expect(cells[3].className).toContain("frequency-heat-level-2"); // 2 of max 4
    expect(cells[4].className).toContain("frequency-heat-level-0"); // 0
    expect(cells[0].getAttribute("title")).toBe("Mon morning: 4 direct trains");
    expect(cells[0].getAttribute("aria-label")).toBe("Mon morning: 4 direct trains");
  });

  it("shows a legend from 0 to the max count with 5 swatches", () => {
    const { container } = renderStrip();
    const legend = container.querySelector(".frequency-heat-legend")!;
    expect(legend.querySelectorAll(".frequency-heat-swatch")).toHaveLength(5);
    const counts = [...legend.querySelectorAll(".frequency-heat-legend-count")].map((el) => el.textContent);
    expect(counts).toEqual(["0", "4"]);
    expect(legend.textContent).toContain("direct trains / daypart");
  });

  it("fires onToggle and wires aria expansion state", () => {
    const onToggle = vi.fn();
    const { container } = renderStrip(onToggle);
    const button = container.querySelector<HTMLButtonElement>(".frequency-heat-strip")!;
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(button.getAttribute("aria-controls")).toBe("legs");
    fireEvent.click(button);
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it("keeps the sampling note beneath the strip", () => {
    const { container } = renderStrip();
    expect(container.querySelector(".frequency-heat-note")!.textContent)
      .toBe("Sampled timetable evidence, not a promise.");
  });
});
