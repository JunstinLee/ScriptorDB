import ConfirmDialog from "./common/ConfirmDialog";
import { FilterConfirmDrawer } from "./FilterConfirmDrawer";
import SettingsModal from "./SettingsModal";
import SwitchingOverlay from "./common/SwitchingOverlay";
import WorkspacePicker from "./WorkspacePicker";
import type {
  ApprovalRequestEvent,
  FilterSchema,
  WorkspaceCreateRequest,
  WorkspaceDetail,
  WorkspaceItem,
  WorkspaceUpdateRequest,
} from "../types";

interface AppDialogsProps {
  workspace: WorkspaceDetail | null;
  workspaces: WorkspaceItem[];
  workspacesError: string | null;
  switchingWorkspace: boolean;
  settingsOpen: boolean;
  onSettingsOpenChange: (open: boolean) => void;
  /** 设置弹窗关闭后调用（用于触发 browser_enabled 重新拉取） */
  onSettingsChanged: () => void;
  showSessionIdHover: boolean;
  setShowSessionIdHover: (v: boolean) => void;
  showSchemaSql: boolean;
  setShowSchemaSql: (v: boolean) => void;
  undoConfirmGroupId: number | null;
  onUndoConfirmClose: () => void;
  onUndoConfirm: () => void;
  approvalRequest: ApprovalRequestEvent | null;
  filterSchema: FilterSchema | null;
  onApprovalSubmit: (
    approved: boolean,
    overrideArgs?: Record<string, Record<string, unknown>>,
  ) => void;
  onSwitchWorkspace: (id: string) => Promise<WorkspaceDetail>;
  onCreateWorkspace: (body: WorkspaceCreateRequest) => Promise<WorkspaceDetail>;
  onRenameWorkspace: (id: string, body: WorkspaceUpdateRequest) => Promise<WorkspaceDetail>;
  onDeleteWorkspace: (id: string, deleteFiles?: boolean) => Promise<void>;
  onRefreshWorkspaces: () => Promise<void>;
  isPickerOpen: boolean;
  onPickerClose: () => void;
  onOpenPicker: () => void;
}

/**
 * 全部弹窗/覆盖层容器：
 * SettingsModal、撤销确认、审批（FilterConfirmDrawer / ConfirmDialog）、
 * WorkspacePicker、SwitchingOverlay。
 * 只负责弹窗的开关与接线，不持有业务状态（设置开关状态由上层传入）。
 */
export default function AppDialogs({
  workspace,
  workspaces,
  workspacesError,
  switchingWorkspace,
  settingsOpen,
  onSettingsOpenChange,
  onSettingsChanged,
  showSessionIdHover,
  setShowSessionIdHover,
  showSchemaSql,
  setShowSchemaSql,
  undoConfirmGroupId,
  onUndoConfirmClose,
  onUndoConfirm,
  approvalRequest,
  filterSchema,
  onApprovalSubmit,
  onSwitchWorkspace,
  onCreateWorkspace,
  onRenameWorkspace,
  onDeleteWorkspace,
  onRefreshWorkspaces,
  isPickerOpen,
  onPickerClose,
  onOpenPicker,
}: AppDialogsProps) {
  const handlePickerCreate = async (body: WorkspaceCreateRequest) => {
    const detail = await onCreateWorkspace(body);
    onPickerClose();
    await onRefreshWorkspaces();
    return detail;
  };

  const handlePickerRename = async (id: string, body: WorkspaceUpdateRequest) => {
    const detail = await onRenameWorkspace(id, body);
    await onRefreshWorkspaces();
    return detail;
  };

  const handlePickerDelete = async (id: string, deleteFiles?: boolean) => {
    await onDeleteWorkspace(id, deleteFiles);
    await onRefreshWorkspaces();
  };

  return (
    <>
      <SettingsModal
        isOpen={settingsOpen}
        onOpenChange={(open) => {
          if (!open) onSettingsChanged();
          onSettingsOpenChange(open);
        }}
        showSessionIdHover={showSessionIdHover}
        setShowSessionIdHover={setShowSessionIdHover}
        showSchemaSql={showSchemaSql}
        setShowSchemaSql={setShowSchemaSql}
        activeWorkspace={workspace}
        workspacesCount={workspaces.length}
        onWorkspaceChanged={onRefreshWorkspaces}
        onOpenWorkspacePicker={onOpenPicker}
      />

      <ConfirmDialog
        isOpen={undoConfirmGroupId !== null}
        onClose={onUndoConfirmClose}
        onConfirm={onUndoConfirm}
        title="Undo to here"
        message="This action will undo all database changes made from the current turn onward and delete the current turn and all subsequent chat history."
        confirmLabel="Undo"
      />

      {approvalRequest !== null &&
      approvalRequest.calls[0]?.tool_name === "browser_apply_filter" ? (
        <FilterConfirmDrawer
          request={approvalRequest}
          schema={filterSchema}
          onApprove={(overrideArgs) => onApprovalSubmit(true, overrideArgs)}
          onReject={() => onApprovalSubmit(false)}
        />
      ) : (
        <ConfirmDialog
          isOpen={approvalRequest !== null}
          onClose={() => onApprovalSubmit(false)}
          onConfirm={() => onApprovalSubmit(true)}
          title="Confirm Import"
          message={
            approvalRequest
              ? `${approvalRequest.calls[0]?.tool_name ?? "import"} will write ${approvalRequest.calls[0]?.row_count ?? ""} row(s) into table ${approvalRequest.calls[0]?.table_name ?? ""}. Proceed?`
              : ""
          }
          confirmLabel="Confirm"
        />
      )}

      <WorkspacePicker
        workspaces={workspaces}
        activeWorkspace={workspace}
        error={workspacesError}
        onActivate={onSwitchWorkspace}
        onCreate={handlePickerCreate}
        onRename={handlePickerRename}
        onDelete={handlePickerDelete}
        onRefresh={onRefreshWorkspaces}
        onCancelActive={onPickerClose}
        isOpen={isPickerOpen || !workspace}
        onClose={onPickerClose}
        isClosable={!!workspace}
      />

      {switchingWorkspace && <SwitchingOverlay />}
    </>
  );
}
