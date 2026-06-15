import { describe, expect, it, vi } from "vitest";
import {
  deriveTitle,
  metaFromListItem,
  readStoredActiveSession,
  writeStoredActiveSession,
} from "./sessions";

describe("deriveTitle", () => {
  it('returns default for empty messages', () => {
    expect(deriveTitle([])).toBe("New Chat");
  });

  it("returns default when no user message exists", () => {
    expect(
      deriveTitle([{ role: "assistant", content: "Hello" }]),
    ).toBe("New Chat");
  });

  it("returns default when user message is empty", () => {
    expect(
      deriveTitle([{ role: "user", content: "" }]),
    ).toBe("New Chat");
  });

  it("returns first user message trimmed", () => {
    expect(
      deriveTitle([
        { role: "assistant", content: "ignored" },
        { role: "user", content: "  What is SQL?  " },
      ]),
    ).toBe("What is SQL?");
  });

  it("truncates long titles", () => {
    const long = "A".repeat(50);
    const result = deriveTitle([{ role: "user", content: long }]);
    expect(result).toBe("A".repeat(24) + "…");
  });

  it("collapses whitespace in title", () => {
    const result = deriveTitle([
      { role: "user", content: "Hello   world\t\ttest" },
    ]);
    expect(result).toBe("Hello world test");
  });
});

describe("metaFromListItem", () => {
  it("uses item title when present", () => {
    const item = {
      session_id: "abc",
      created_at: "2025-01-01T00:00:00Z",
      last_access: "2025-01-02T00:00:00Z",
      message_count: 3,
      title: "My Chat",
    };
    const result = metaFromListItem(item, "fallback");
    expect(result).toEqual({
      session_id: "abc",
      created_at: "2025-01-01T00:00:00Z",
      title: "My Chat",
    });
  });

  it("uses fallback title when item title is null", () => {
    const item = {
      session_id: "abc",
      created_at: "2025-01-01T00:00:00Z",
      last_access: "2025-01-02T00:00:00Z",
      message_count: 0,
      title: null,
    };
    const result = metaFromListItem(item, "fallback");
    expect(result).toEqual({
      session_id: "abc",
      created_at: "2025-01-01T00:00:00Z",
      title: "fallback",
    });
  });
});

describe("readStoredActiveSession", () => {
  it("returns null when nothing stored", () => {
    expect(readStoredActiveSession()).toBeNull();
  });

  it("returns stored session id", () => {
    localStorage.setItem("scriptordb:active_session_id", "session-123");
    expect(readStoredActiveSession()).toBe("session-123");
  });

  it("returns null when localStorage throws", () => {
    const original = localStorage.getItem;
    localStorage.getItem = () => {
      throw new Error("quota exceeded");
    };
    try {
      expect(readStoredActiveSession()).toBeNull();
    } finally {
      localStorage.getItem = original;
    }
  });
});

describe("writeStoredActiveSession", () => {
  it("stores session id", () => {
    writeStoredActiveSession("session-456");
    expect(localStorage.getItem("scriptordb:active_session_id")).toBe(
      "session-456",
    );
  });

  it("removes key when id is null", () => {
    localStorage.setItem("scriptordb:active_session_id", "existing");
    writeStoredActiveSession(null);
    expect(localStorage.getItem("scriptordb:active_session_id")).toBeNull();
  });

  it("does not throw when localStorage.setItem throws", () => {
    const original = localStorage.setItem;
    localStorage.setItem = () => {
      throw new Error("quota exceeded");
    };
    try {
      expect(() => writeStoredActiveSession("test")).not.toThrow();
    } finally {
      localStorage.setItem = original;
    }
  });
});
