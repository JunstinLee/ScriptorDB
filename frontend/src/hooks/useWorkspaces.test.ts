import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useWorkspaces } from "./useWorkspaces";
import {
  WorkspaceNotSelectedError,
} from "../api/client";

const {
  mockFetchWorkspaces,
  mockFetchActiveWorkspace,
  mockActivateWorkspace,
  mockCreateWorkspace,
  mockDeleteWorkspace,
  mockUpdateWorkspace,
} = vi.hoisted(() => ({
  mockFetchWorkspaces: vi.fn(),
  mockFetchActiveWorkspace: vi.fn(),
  mockActivateWorkspace: vi.fn(),
  mockCreateWorkspace: vi.fn(),
  mockDeleteWorkspace: vi.fn(),
  mockUpdateWorkspace: vi.fn(),
}));

vi.mock("../api/client", () => ({
  fetchWorkspaces: mockFetchWorkspaces,
  fetchActiveWorkspace: mockFetchActiveWorkspace,
  activateWorkspace: mockActivateWorkspace,
  createWorkspace: mockCreateWorkspace,
  deleteWorkspace: mockDeleteWorkspace,
  updateWorkspace: mockUpdateWorkspace,
  WorkspaceNotSelectedError: class extends Error {
    constructor() {
      super("WORKSPACE_NOT_SELECTED");
      this.name = "WorkspaceNotSelectedError";
    }
  },
}));

const sampleWs: import("../types").WorkspaceDetail = {
  id: "ws_abc",
  name: "Test Project",
  path: "/tmp/test-ws",
  created_at: "2026-06-23T00:00:00Z",
  db_url: "sqlite:////tmp/test-ws/db.sqlite",
  llm_provider: "openai",
  llm_model: "gpt-4o",
};

beforeEach(() => {
  mockFetchWorkspaces.mockReset();
  mockFetchActiveWorkspace.mockReset();
  mockActivateWorkspace.mockReset();
  mockCreateWorkspace.mockReset();
  mockDeleteWorkspace.mockReset();
  mockUpdateWorkspace.mockReset();
  localStorage.clear();
});

describe("useWorkspaces", () => {
  it("loads active workspace on mount", async () => {
    mockFetchWorkspaces.mockResolvedValueOnce({ workspaces: [sampleWs] });
    mockFetchActiveWorkspace.mockResolvedValueOnce(sampleWs);

    const { result } = renderHook(() => useWorkspaces());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.activeWorkspace).toEqual(sampleWs);
    expect(result.current.workspaces).toEqual([sampleWs]);
    expect(result.current.needsWorkspace).toBe(false);
    expect(localStorage.getItem("scriptordb:active_workspace_id")).toBe(
      "ws_abc",
    );
  });

  it("sets needsWorkspace=true when active endpoint returns null", async () => {
    mockFetchWorkspaces.mockResolvedValueOnce({ workspaces: [] });
    mockFetchActiveWorkspace.mockResolvedValueOnce(null);

    const { result } = renderHook(() => useWorkspaces());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.activeWorkspace).toBeNull();
    expect(result.current.needsWorkspace).toBe(true);
  });

  it("sets needsWorkspace=true when active endpoint throws 409", async () => {
    mockFetchWorkspaces.mockResolvedValueOnce({ workspaces: [] });
    mockFetchActiveWorkspace.mockRejectedValueOnce(
      new WorkspaceNotSelectedError(""),
    );

    const { result } = renderHook(() => useWorkspaces());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.activeWorkspace).toBeNull();
    expect(result.current.needsWorkspace).toBe(true);
  });

  it("createAndActivate creates and switches to new workspace", async () => {
    mockFetchWorkspaces.mockResolvedValueOnce({ workspaces: [] });
    mockFetchActiveWorkspace.mockResolvedValueOnce(null);
    mockCreateWorkspace.mockResolvedValueOnce({
      id: sampleWs.id,
      name: sampleWs.name,
      path: sampleWs.path,
      created_at: sampleWs.created_at,
    });
    mockActivateWorkspace.mockResolvedValueOnce(sampleWs);

    const { result } = renderHook(() => useWorkspaces());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    let created: typeof sampleWs | undefined;
    await act(async () => {
      created = await result.current.createAndActivate({
        name: "Test Project",
        path: "/tmp/test-ws",
      });
    });

    expect(created).toEqual(sampleWs);
    expect(result.current.activeWorkspace).toEqual(sampleWs);
    expect(result.current.workspaces).toEqual([
      {
        id: sampleWs.id,
        name: sampleWs.name,
        path: sampleWs.path,
        created_at: sampleWs.created_at,
      },
    ]);
    expect(result.current.needsWorkspace).toBe(false);
  });

  it("switchWorkspace updates the active workspace", async () => {
    mockFetchWorkspaces.mockResolvedValueOnce({ workspaces: [sampleWs] });
    mockFetchActiveWorkspace.mockResolvedValueOnce(sampleWs);
    mockActivateWorkspace.mockResolvedValueOnce({
      ...sampleWs,
      name: "Other",
    });

    const { result } = renderHook(() => useWorkspaces());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    let detail: typeof sampleWs | undefined;
    await act(async () => {
      detail = await result.current.switchWorkspace("ws_abc");
    });

    expect(detail?.name).toBe("Other");
    expect(result.current.activeWorkspace?.name).toBe("Other");
    expect(localStorage.getItem("scriptordb:active_workspace_id")).toBe(
      "ws_abc",
    );
  });

  it("removeWorkspace drops the entry and clears active if matched", async () => {
    mockFetchWorkspaces.mockResolvedValueOnce({ workspaces: [sampleWs] });
    mockFetchActiveWorkspace.mockResolvedValueOnce(sampleWs);
    mockDeleteWorkspace.mockResolvedValueOnce({ ok: true });

    const { result } = renderHook(() => useWorkspaces());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.removeWorkspace("ws_abc");
    });

    expect(result.current.workspaces).toEqual([]);
    expect(result.current.activeWorkspace).toBeNull();
    expect(localStorage.getItem("scriptordb:active_workspace_id")).toBeNull();
  });

  it("renameWorkspace updates the name in workspaces list", async () => {
    mockFetchWorkspaces.mockResolvedValueOnce({ workspaces: [sampleWs] });
    mockFetchActiveWorkspace.mockResolvedValueOnce(sampleWs);
    mockUpdateWorkspace.mockResolvedValueOnce({
      ...sampleWs,
      name: "Renamed",
    });

    const { result } = renderHook(() => useWorkspaces());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    let detail: typeof sampleWs | undefined;
    await act(async () => {
      detail = await result.current.renameWorkspace("ws_abc", {
        name: "Renamed",
      });
    });

    expect(detail?.name).toBe("Renamed");
    expect(result.current.workspaces[0].name).toBe("Renamed");
    expect(result.current.activeWorkspace?.name).toBe("Renamed");
  });
});
