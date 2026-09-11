import { describe, expect, it, beforeEach } from "vitest";
import {
  createSession,
  listSessions,
  getSession,
  deleteSession,
  getSchema,
} from "./sessions";

import { stubFetch } from "../test/mockClient";

const { json: mockJson, fetch: mockFetch } = stubFetch();

beforeEach(() => {
  mockFetch.mockClear();
});

describe("createSession", () => {
  it("sends POST to /api/sessions", async () => {
    mockJson.mockResolvedValueOnce({ session_id: "new-id" });
    const result = await createSession();
    expect(result).toEqual({ session_id: "new-id" });
    expect(mockFetch).toHaveBeenCalledWith("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
  });
});

describe("listSessions", () => {
  it("sends GET to /api/sessions", async () => {
    mockJson.mockResolvedValueOnce({ sessions: [] });
    const result = await listSessions();
    expect(result).toEqual({ sessions: [] });
    expect(mockFetch).toHaveBeenCalledWith("/api/sessions", {
      headers: { "Content-Type": "application/json" },
    });
  });
});

describe("getSession", () => {
  it("sends GET to /api/sessions/:id", async () => {
    mockJson.mockResolvedValueOnce({ session_id: "abc", messages: [] });
    const result = await getSession("abc");
    expect(result).toEqual({ session_id: "abc", messages: [] });
    expect(mockFetch).toHaveBeenCalledWith("/api/sessions/abc", {
      headers: { "Content-Type": "application/json" },
    });
  });
});

describe("deleteSession", () => {
  it("sends DELETE to /api/sessions/:id", async () => {
    mockJson.mockResolvedValueOnce({ ok: true });
    const result = await deleteSession("abc");
    expect(result).toEqual({ ok: true });
    expect(mockFetch).toHaveBeenCalledWith("/api/sessions/abc", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    });
  });
});

describe("getSchema", () => {
  it("sends GET to /api/schema", async () => {
    mockJson.mockResolvedValueOnce({ tables: [{ name: "users", sql: "..." }] });
    const result = await getSchema();
    expect(result).toEqual({ tables: [{ name: "users", sql: "..." }] });
    expect(mockFetch).toHaveBeenCalledWith("/api/schema", {
      headers: { "Content-Type": "application/json" },
    });
  });
});
