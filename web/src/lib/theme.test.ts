import { describe, expect, it } from "vitest";
import { parseStoredTheme, resolveTheme, toggledTheme } from "./theme";

describe("parseStoredTheme", () => {
  it("accepts the two valid values", () => {
    expect(parseStoredTheme("light")).toBe("light");
    expect(parseStoredTheme("dark")).toBe("dark");
  });
  it("treats anything else as no stored choice", () => {
    expect(parseStoredTheme(null)).toBeNull();
    expect(parseStoredTheme("")).toBeNull();
    expect(parseStoredTheme("auto")).toBeNull();
  });
});

describe("resolveTheme", () => {
  it("explicit choice wins over the system", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
  it("no choice follows the system", () => {
    expect(resolveTheme(null, true)).toBe("dark");
    expect(resolveTheme(null, false)).toBe("light");
  });
});

describe("toggledTheme", () => {
  it("flips", () => {
    expect(toggledTheme("light")).toBe("dark");
    expect(toggledTheme("dark")).toBe("light");
  });
});
