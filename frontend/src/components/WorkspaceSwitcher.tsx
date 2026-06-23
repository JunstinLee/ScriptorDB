import { useCallback } from "react";
import { Popover } from "@heroui/react";
import { ChevronDown, Folder, Plus, Settings as SettingsIcon } from "lucide-react";
import type { WorkspaceDetail, WorkspaceItem } from "../types";

interface WorkspaceSwitcherProps {
  activeWorkspace: WorkspaceDetail;
  workspaces: WorkspaceItem[];
  disabled?: boolean;
  onSwitch: (id: string) => void;
  onOpenSettings: () => void;
  onRequestNew: () => void;
}

export default function WorkspaceSwitcher({
  activeWorkspace,
  workspaces,
  disabled,
  onSwitch,
  onOpenSettings,
  onRequestNew,
}: WorkspaceSwitcherProps) {
  const handleSelect = useCallback(
    (id: string) => {
      if (id === activeWorkspace.id) return;
      onSwitch(id);
    },
    [activeWorkspace.id, onSwitch],
  );

  const others = workspaces.filter((w) => w.id !== activeWorkspace.id);

  return (
    <Popover>
      <Popover.Trigger>
        <button
          type="button"
          disabled={disabled}
          className="flex items-center gap-1.5 rounded-lg border bg-surface px-2 py-1 text-xs outline-none hover:border-accent/40 disabled:opacity-50"
          aria-label="Switch workspace"
        >
          <Folder className="size-3.5 text-muted" />
          <span className="max-w-[10rem] truncate font-medium">
            {activeWorkspace.name}
          </span>
          <ChevronDown className="size-3.5 text-muted" />
        </button>
      </Popover.Trigger>
      <Popover.Content className="w-72 p-0">
        <Popover.Dialog className="p-1">
          <div className="px-2 py-1.5 text-xs text-muted">
            Current workspace
          </div>
          <div className="rounded-md bg-accent/10 px-2 py-1.5">
            <div className="truncate text-sm font-medium">
              {activeWorkspace.name}
            </div>
            <div
              className="truncate text-xs text-muted font-mono"
              title={activeWorkspace.path}
            >
              {activeWorkspace.path}
            </div>
          </div>

          {others.length > 0 && (
            <>
              <div className="mt-2 px-2 py-1.5 text-xs text-muted">
                Switch to
              </div>
              <ul className="flex flex-col gap-0.5">
                {others.map((w) => (
                  <li key={w.id}>
                    <button
                      type="button"
                      className="flex w-full flex-col items-start rounded-md px-2 py-1.5 text-left text-sm hover:bg-default/50"
                      onClick={() => handleSelect(w.id)}
                    >
                      <span className="truncate font-medium">{w.name}</span>
                      <span
                        className="truncate text-xs text-muted font-mono"
                        title={w.path}
                      >
                        {w.path}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}

          <div className="mt-2 flex flex-col gap-0.5 border-t pt-2">
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-default/50"
              onClick={onRequestNew}
            >
              <Plus className="size-3.5" /> New workspace
            </button>
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-default/50"
              onClick={onOpenSettings}
            >
              <SettingsIcon className="size-3.5" /> Manage workspaces
            </button>
          </div>
        </Popover.Dialog>
      </Popover.Content>
    </Popover>
  );
}
