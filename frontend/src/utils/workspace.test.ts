import { describe, expect, it } from "vitest";
import { formatWorkspacePath } from "./workspace";

describe("formatWorkspacePath", () => {
  it("truncates path before .config on Linux/macOS", () => {
    expect(
      formatWorkspacePath("/Users/gklgkl/.config/scriptordb/abc123"),
    ).toBe(".config/scriptordb/abc123");
  });

  it("truncates path before .config on Windows", () => {
    expect(
      formatWorkspacePath("C:\\Users\\name\\AppData\\Roaming\\.config\\scriptordb"),
    ).toBe(".config\\scriptordb");
  });

  it("returns full path when .config is not present", () => {
    expect(formatWorkspacePath("/var/data/workspace")).toBe(
      "/var/data/workspace",
    );
  });

  it("returns empty string for null", () => {
    expect(formatWorkspacePath(null)).toBe("");
  });

  it("returns empty string for undefined", () => {
    expect(formatWorkspacePath(undefined)).toBe("");
  });

  it("returns empty string for empty input", () => {
    expect(formatWorkspacePath("")).toBe("");
  });

  it("truncates at the first occurrence of .config", () => {
    expect(
      formatWorkspacePath("/home/user/.config/sub/.config/nested"),
    ).toBe(".config/sub/.config/nested");
  });
});
