import { t } from "../i18n";
import ApiKeyRequiredModal from "./ApiKeyRequiredModal";
import ConfirmDialog from "./common/ConfirmDialog";
import { FilterConfirmDrawer } from "./FilterConfirmDrawer";
import SettingsModal from "./SettingsModal";
import SwitchingOverlay from "./common/SwitchingOverlay";
import WorkspacePicker from "./WorkspacePicker";
import type {
  ApprovalRequestEvent,
  ApiKeyStatusKind,
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
  /** 主动检测到的 API Key 状态（见 useApiKeyStatus） */
  apiKeyKind: ApiKeyStatusKind | null;
  apiKeyProvider: string | null;
  apiKeyError: string | null;
  onApiKeyResolved: () => void;
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
  apiKeyKind,
  apiKeyProvider,
  apiKeyError,
  onApiKeyResolved,
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

      <ApiKeyRequiredModal
        isOpen={
          !!workspace &&
          !settingsOpen &&
          (apiKeyKind === "missing" ||
            apiKeyKind === "invalid" ||
            apiKeyKind === "unknown")
        }
        status={apiKeyKind}
        provider={apiKeyProvider}
        error={apiKeyError}
        onResolved={onApiKeyResolved}
      />

      <ConfirmDialog
        isOpen={undoConfirmGroupId !== null}
        onClose={onUndoConfirmClose}
        onConfirm={onUndoConfirm}
        title={t("chat.undo_dialog.title")}
        message={t("chat.undo_dialog.message")}
        confirmLabel={t("chat.undo")}
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
          title={t("chat.import_dialog.title")}
          message={
            approvalRequest
              ? t("chat.import_dialog.message", {
                  tool:
                    approvalRequest.calls[0]?.tool_name ??
                    t("chat.import_dialog.tool_fallback"),
                  count: approvalRequest.calls[0]?.row_count ?? 0,
                  table: approvalRequest.calls[0]?.table_name ?? "",
                })
              : ""
          }
          confirmLabel={t("common.confirm")}
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
