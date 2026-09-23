// web/src/legalPages.test.ts
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const page = (name: string) =>
  readFileSync(new URL(`../public/${name}`, import.meta.url), "utf8");

const ENCODED_EMAIL =
  "&#99;&#111;&#110;&#116;&#97;&#99;&#116;&#64;&#111;&#110;&#101;&#115;&#116;&#111;&#112;&#101;&#117;&#114;&#111;&#112;&#101;&#46;&#101;&#117;";

describe("legal pages", () => {
  for (const name of ["legal.html", "privacy.html"]) {
    it(`${name} is script-free and never spells out the email`, () => {
      const html = page(name);
      expect(html).not.toMatch(/<script/i);
      expect(html).not.toContain("contact@onestopeurope.eu");
      expect(html).toContain('href="/"');
    });
  }

  it("legal notice identifies the operator", () => {
    const html = page("legal.html");
    for (const text of ["Aaron Bussche", "Sophiaweg 76", "6523 NJ Nijmegen", "Netherlands",
      ENCODED_EMAIL, "https://aaronbussche.eu", "KvK", 'id="affiliate-links"', 'href="/privacy.html"']) {
      expect(html).toContain(text);
    }
  });

  it("privacy policy covers every processing we do", () => {
    const html = page("privacy.html");
    for (const text of ["No cookies", "IP address", "OpenFreeMap", "Trainline", "Partnerize",
      "Autoriteit Persoonsgegevens", 'href="/legal.html"']) {
      expect(html).toContain(text);
    }
  });
});
