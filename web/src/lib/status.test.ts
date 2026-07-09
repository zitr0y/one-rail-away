import { describe, expect, it } from "vitest";
import { statusText } from "./status";

describe("statusText", () => {
  it("is null with no origin", () => {
    expect(statusText(null, null)).toBeNull();
    expect(statusText(null, "Praha hl.n.")).toBeNull();
  });

  it("names the selected origin", () => {
    expect(statusText("Wien Hbf", null)).toBe("From Wien Hbf — click a dot for details");
  });

  it("names the full route once a destination is picked", () => {
    expect(statusText("Wien Hbf", "Budapest-Keleti")).toBe("Wien Hbf → Budapest-Keleti");
  });
});
