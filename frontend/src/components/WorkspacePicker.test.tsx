import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import WorkspacePicker from "./WorkspacePicker";
import type {
  WorkspaceCreateRequest,
  WorkspaceDetail,
  WorkspaceItem,
  WorkspaceUpdateRequest,
} from "../types";

const noopActivate = (_id: string): Promise<WorkspaceDetail> =>
  Promise.resolve({} as WorkspaceDetail);
const noopCreate = (_body: WorkspaceCreateRequest): Promise<WorkspaceDetail> =>
  Promise.resolve({} as WorkspaceDetail);
const noopRename = (
  _id: string,
  _body: WorkspaceUpdateRequest,
): Promise<WorkspaceDetail> => Promise.resolve({} as WorkspaceDetail);
const noopDelete = (_id: string, _deleteFiles?: boolean): Promise<void> =>
  Promise.resolve();
const noopRefresh = (): Promise<void> => Promise.resolve();
const noopCancel = (): void => {
  /* noop */
};
const noopClose = (): void => {
  /* noop */
};

const sampleWorkspaces: WorkspaceItem[] = [
  {
    id: "ws_a",
    name: "Project A",
    path: "/tmp/a",
    created_at: "2026-06-23T00:00:00Z",
  },
  {
    id: "ws_b",
    name: "Project B",
    path: "/tmp/b",
    created_at: "2026-06-23T00:00:00Z",
  },
];

beforeEach(() => {
  localStorage.clear();
});

describe("WorkspacePicker", () => {
  it("renders existing workspaces when open", () => {
    render(
      <WorkspacePicker
        workspaces={sampleWorkspaces}
        activeWorkspace={null}
        error={null}
        onActivate={noopActivate}
        onCreate={noopCreate}
        onRename={noopRename}
        onDelete={noopDelete}
        onRefresh={noopRefresh}
        onCancelActive={noopCancel}
        isOpen={true}
        onClose={noopClose}
        isClosable={true}
      />,
    );

    expect(screen.getByText("Project A")).toBeTruthy();
    expect(screen.getByText("Project B")).toBeTruthy();
  });

  it("shows empty state when no workspaces exist", () => {
    render(
      <WorkspacePicker
        workspaces={[]}
        activeWorkspace={null}
        error={null}
        onActivate={noopActivate}
        onCreate={noopCreate}
        onRename={noopRename}
        onDelete={noopDelete}
        onRefresh={noopRefresh}
        onCancelActive={noopCancel}
        isOpen={true}
        onClose={noopClose}
        isClosable={true}
      />,
    );

    expect(screen.getByText(/no workspaces\./i)).toBeTruthy();
  });

  it("calls onActivate when a workspace's Open button is pressed", async () => {
    const onActivate = vi.fn().mockResolvedValue({} as never);
    render(
      <WorkspacePicker
        workspaces={sampleWorkspaces}
        activeWorkspace={null}
        error={null}
        onActivate={onActivate}
        onCreate={noopCreate}
        onRename={noopRename}
        onDelete={noopDelete}
        onRefresh={noopRefresh}
        onCancelActive={noopCancel}
        isOpen={true}
        onClose={noopClose}
        isClosable={true}
      />,
    );

    const openButtons = screen.getAllByRole("button", { name: /open/i });
    fireEvent.click(openButtons[0]);

    await waitFor(() => {
      expect(onActivate).toHaveBeenCalledWith("ws_a");
    });
  });

  it("calls onCreate with name only on submit", async () => {
    const onCreate = vi.fn().mockResolvedValue({} as never);
    render(
      <WorkspacePicker
        workspaces={[]}
        activeWorkspace={null}
        error={null}
        onActivate={noopActivate}
        onCreate={onCreate}
        onRename={noopRename}
        onDelete={noopDelete}
        onRefresh={noopRefresh}
        onCancelActive={noopCancel}
        isOpen={true}
        onClose={noopClose}
        isClosable={true}
      />,
    );

    const nameInput = screen.getByLabelText(/name/i) as HTMLInputElement;

    fireEvent.change(nameInput, { target: { value: "New WS" } });

    const submit = screen.getByRole("button", { name: /create workspace/i });
    fireEvent.click(submit);

    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith({
        name: "New WS",
        db_url: null,
      });
    });
  });

  it("displays an error banner when error is provided", () => {
    render(
      <WorkspacePicker
        workspaces={[]}
        activeWorkspace={null}
        error="boom"
        onActivate={noopActivate}
        onCreate={noopCreate}
        onRename={noopRename}
        onDelete={noopDelete}
        onRefresh={noopRefresh}
        onCancelActive={noopCancel}
        isOpen={true}
        onClose={noopClose}
        isClosable={true}
      />,
    );

    expect(screen.getByText("boom")).toBeTruthy();
  });

  it("does not show rename or delete buttons for active workspace", () => {
    render(
      <WorkspacePicker
        workspaces={sampleWorkspaces}
        activeWorkspace={{
          ...sampleWorkspaces[0],
          db_url: "sqlite:///test.db",
          llm_provider: "openai",
          llm_model: null,
        }}
        error={null}
        onActivate={noopActivate}
        onCreate={noopCreate}
        onRename={noopRename}
        onDelete={noopDelete}
        onRefresh={noopRefresh}
        onCancelActive={noopCancel}
        isOpen={true}
        onClose={noopClose}
        isClosable={true}
      />,
    );

    expect(screen.getByText(/active/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /rename project a/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /delete project a/i })).toBeNull();
  });

  it("does not render when isOpen is false", () => {
    render(
      <WorkspacePicker
        workspaces={sampleWorkspaces}
        activeWorkspace={null}
        error={null}
        onActivate={noopActivate}
        onCreate={noopCreate}
        onRename={noopRename}
        onDelete={noopDelete}
        onRefresh={noopRefresh}
        onCancelActive={noopCancel}
        isOpen={false}
        onClose={noopClose}
        isClosable={true}
      />,
    );

    expect(screen.queryByText("Workspaces")).toBeNull();
  });
});
