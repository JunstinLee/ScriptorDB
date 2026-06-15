import { describe, expect, it, vi } from "vitest";
import { request } from "./core";

const mockJson = vi.fn(() => Promise.resolve({ ok: true }));
const mockText = vi.fn(() => Promise.resolve("error body"));
const mockFetch = vi.fn(() =>
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
});
