import { describe, expect, it, vi, beforeEach } from "vitest";
import { request, WorkspaceNotSelectedError, ApiError } from "./core";

const mockJson: ReturnType<typeof vi.fn> = vi.fn(() =>
  Promise.resolve({ ok: true }),
);
const mockText: ReturnType<typeof vi.fn> = vi.fn(() =>
  Promise.resolve("error body"),
);
const mockFetch: ReturnType<typeof vi.fn> = vi.fn(() =>
  Promise.resolve({ ok: true, json: mockJson, text: mockText, status: 200 }),
);

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockClear();
  mockJson.mockClear();
  mockText.mockClear();
});

describe("request (core)", () => {
  it("prepends /api to URL", async () => {
    mockJson.mockResolvedValueOnce({ data: 42 });
    const result = await request<{ data: number }>("/test");
    expect(result).toEqual({ data: 42 });
    expect(mockFetch).toHaveBeenCalledWith("/api/test", {
      headers: { "Content-Type": "application/json" },
    });
  });

  it("merges custom options", async () => {
    mockJson.mockResolvedValueOnce({});
    await request("/test", {
      method: "POST",
      body: JSON.stringify({ key: "val" }),
    });
    expect(mockFetch).toHaveBeenCalledWith("/api/test", {
      headers: { "Content-Type": "application/json" },
      method: "POST",
      body: JSON.stringify({ key: "val" }),
    });
  });

  it("throws on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: mockJson,
      text: mockText,
    });
    mockText.mockResolvedValueOnce("Internal Server Error");
    await expect(request("/fail")).rejects.toThrow(
      "HTTP 500: Internal Server Error",
    );
  });

  it("throws with fallback text when body cannot be read", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: mockJson,
      text: vi.fn(() => Promise.reject(new Error("body unreadable"))),
    });
    await expect(request("/missing")).rejects.toThrow("HTTP 404: Unknown error");
  });

  it("throws WorkspaceNotSelectedError on 409 with WORKSPACE_NOT_SELECTED", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: mockJson,
      text: vi
        .fn()
        .mockResolvedValueOnce(
          JSON.stringify({ detail: "No active workspace", code: "WORKSPACE_NOT_SELECTED" }),
        ),
    });
    await expect(request("/workspaces/active")).rejects.toBeInstanceOf(
      WorkspaceNotSelectedError,
    );
  });

  it("throws ApiError (not WorkspaceNotSelectedError) on plain 409", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: mockJson,
      text: vi.fn().mockResolvedValueOnce("Conflict"),
    });
    const err = await request("/something").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).not.toBeInstanceOf(WorkspaceNotSelectedError);
  });
});
