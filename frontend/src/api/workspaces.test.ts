import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  fetchWorkspaces,
  fetchActiveWorkspace,
  createWorkspace,
  getWorkspace,
  activateWorkspace,
  updateWorkspace,
  deleteWorkspace,
} from "./workspaces";

const mockJson = vi.fn(() => Promise.resolve({}));
const mockText = vi.fn(() => Promise.resolve(""));
const mockFetch = vi.fn(() =>
  Promise.resolve({ ok: true, json: mockJson, text: mockText, status: 200 }),
);

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockClear();
  mockJson.mockClear();
});

const sampleDetail = {
  id: "ws_abc",
  name: "Test",
  path: "/tmp/test",
  created_at: "2026-06-23T00:00:00Z",
  db_url: "sqlite:////tmp/test/db.sqlite",
  llm_provider: "openai",
  llm_model: "gpt-4o",
};

describe("fetchWorkspaces", () => {
  it("fetches /api/workspaces", async () => {
    mockJson.mockResolvedValueOnce({ workspaces: [] });
    const result = await fetchWorkspaces();
    expect(result).toEqual({ workspaces: [] });
    expect(mockFetch).toHaveBeenCalledWith("/api/workspaces", {
      headers: { "Content-Type": "application/json" },
    });
  });
});

describe("fetchActiveWorkspace", () => {
  it("returns the workspace when present", async () => {
    mockJson.mockResolvedValueOnce({ workspace: sampleDetail });
    const result = await fetchActiveWorkspace();
    expect(result).toEqual(sampleDetail);
  });

  it("returns null when none is active", async () => {
    mockJson.mockResolvedValueOnce({ workspace: null });
    const result = await fetchActiveWorkspace();
    expect(result).toBeNull();
  });
});

describe("createWorkspace", () => {
  it("POSTs body to /api/workspaces", async () => {
    mockJson.mockResolvedValueOnce({ ...sampleDetail });
    const result = await createWorkspace({
      name: "Test",
      path: "/tmp/test",
      db_url: null,
    });
    expect(result).toEqual(sampleDetail);
    expect(mockFetch).toHaveBeenCalledWith("/api/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "Test",
        path: "/tmp/test",
        db_url: null,
      }),
    });
  });
});

describe("getWorkspace", () => {
  it("GETs /api/workspaces/:id", async () => {
    mockJson.mockResolvedValueOnce(sampleDetail);
    const result = await getWorkspace("ws_abc");
    expect(result).toEqual(sampleDetail);
    expect(mockFetch).toHaveBeenCalledWith("/api/workspaces/ws_abc", {
      headers: { "Content-Type": "application/json" },
    });
  });
});

describe("activateWorkspace", () => {
  it("POSTs to /api/workspaces/:id/activate", async () => {
    mockJson.mockResolvedValueOnce(sampleDetail);
    const result = await activateWorkspace("ws_abc");
    expect(result).toEqual(sampleDetail);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/workspaces/ws_abc/activate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace_id: "ws_abc" }),
      },
    );
  });
});

describe("updateWorkspace", () => {
  it("PATCHes /api/workspaces/:id with body", async () => {
    mockJson.mockResolvedValueOnce({ ...sampleDetail, name: "Renamed" });
    const result = await updateWorkspace("ws_abc", { name: "Renamed" });
    expect(result.name).toBe("Renamed");
    expect(mockFetch).toHaveBeenCalledWith("/api/workspaces/ws_abc", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Renamed" }),
    });
  });
});

describe("deleteWorkspace", () => {
  it("DELETEs /api/workspaces/:id without flag", async () => {
    mockJson.mockResolvedValueOnce({ ok: true });
    const result = await deleteWorkspace("ws_abc");
    expect(result).toEqual({ ok: true });
    expect(mockFetch).toHaveBeenCalledWith("/api/workspaces/ws_abc", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    });
  });

  it("adds ?delete_files=true when requested", async () => {
    mockJson.mockResolvedValueOnce({ ok: true });
    await deleteWorkspace("ws_abc", true);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/workspaces/ws_abc?delete_files=true",
      {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
      },
    );
  });
});
