import { describe, expect, it } from "vitest";

import { faviconUrl } from "../lib/favicon";

describe("faviconUrl", () => {
  it("derives a favicon URL from a full URL's hostname", () => {
    expect(faviconUrl("https://example.com/posts/123", 32)).toBe(
      "https://www.google.com/s2/favicons?domain=example.com&sz=32"
    );
  });

  it("accepts a bare host without a scheme", () => {
    expect(faviconUrl("example.com")).toBe(
      "https://www.google.com/s2/favicons?domain=example.com&sz=32"
    );
  });

  it("honours the requested size", () => {
    expect(faviconUrl("https://sub.example.org", 64)).toBe(
      "https://www.google.com/s2/favicons?domain=sub.example.org&sz=64"
    );
  });

  it("returns an empty string for missing or unusable input", () => {
    expect(faviconUrl(null)).toBe("");
    expect(faviconUrl(undefined)).toBe("");
    expect(faviconUrl("")).toBe("");
    expect(faviconUrl("not a url")).toBe("");
  });
});
