import { describe, expect, it, vi } from "vitest";
import { getSessionDisplayName, formatRelative } from "./display";

describe("getSessionDisplayName", () => {
  it("returns default for null title", () => {
    expect(getSessionDisplayName(null)).toBe("New Chat");
  });

  it("returns default for undefined title", () => {
    expect(getSessionDisplayName(undefined)).toBe("New Chat");
  });

  it("returns default for empty string", () => {
    expect(getSessionDisplayName("")).toBe("New Chat");
  });

  it("returns default for whitespace-only title", () => {
    expect(getSessionDisplayName("   ")).toBe("New Chat");
  });

  it("returns trimmed title when valid", () => {
    expect(getSessionDisplayName("Hello")).toBe("Hello");
  });

  it("trims surrounding whitespace", () => {
    expect(getSessionDisplayName("  Hello World  ")).toBe("Hello World");
  });
});

describe("formatRelative", () => {
  it('returns "just now" for same instant', () => {
    vi.setSystemTime(new Date("2025-06-15T12:00:00Z"));
    expect(formatRelative("2025-06-15T12:00:00Z")).toBe("just now");
  });

  it("returns minutes ago", () => {
    vi.setSystemTime(new Date("2025-06-15T12:05:00Z"));
    expect(formatRelative("2025-06-15T12:00:00Z")).toBe("5m ago");
  });

  it("returns hours ago", () => {
    vi.setSystemTime(new Date("2025-06-15T14:00:00Z"));
    expect(formatRelative("2025-06-15T12:00:00Z")).toBe("2h ago");
  });

  it("returns days ago", () => {
    vi.setSystemTime(new Date("2025-06-17T12:00:00Z"));
    expect(formatRelative("2025-06-15T12:00:00Z")).toBe("2d ago");
  });

  it("returns locale date string for 30+ days", () => {
    vi.setSystemTime(new Date("2025-08-15T12:00:00Z"));
    const result = formatRelative("2025-06-15T12:00:00Z");
    expect(result).toBe(new Date("2025-06-15T12:00:00Z").toLocaleDateString());
  });

  it("handles invalid date string", () => {
    const result = formatRelative("not-a-date");
    expect(typeof result).toBe("string");
  });

  it("handles future dates as just now", () => {
    vi.setSystemTime(new Date("2025-06-15T12:00:00Z"));
    expect(formatRelative("2025-06-15T12:30:00Z")).toBe("just now");
  });
});
