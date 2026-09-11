// Type-only 域模块 barrel：全部 DTO 按域拆分到同目录模块，
// 此处集中再导出，既有 `import type { ... } from "../types"` 调用点无需改动。

export type {
  ActiveRunResponse,
  ApprovalSubmitResponse,
  ChatMessage,
  ChatRequest,
  SessionCreateResponse,
  SessionInfo,
  SessionListItem,
  SessionListResponse,
  SessionMeta,
} from "./session";

export type {
  CanonicalModelItem,
  CanonicalModelsResponse,
  DefaultModelResponse,
  HealthResponse,
  ModelEntry,
  ModelsResponse,
  ModelsWithCanonicalResponse,
  ProviderInfo,
} from "./models";

export type {
  ActiveWorkspaceResponse,
  ApiKeyRequest,
  ApiKeyTestResponse,
  MySQLConfigRequest,
  MySQLConfigResponse,
  SettingsResponse,
  SettingsUpdateRequest,
  WorkspaceActivateRequest,
  WorkspaceCreateRequest,
  WorkspaceDetail,
  WorkspaceItem,
  WorkspaceListResponse,
  WorkspaceUpdateRequest,
} from "./workspace";

export type { SchemaColumn, SchemaResponse, SchemaTable } from "./schema";

export type { Run, ToolInvocation, TraceStep } from "./run";

export type {
  BrowserAction,
  BrowserActionEvent,
  BrowserHistoryEntry,
  BrowserProfileItem,
  BrowserState,
  CookieInfo,
  CookiesResponse,
  InteractByCoordsRequest,
  InteractRequest,
  InteractResponse,
  ProfilesResponse,
  SaveProfileRequest,
  SetCookieRequest,
  TakeoverCancelRequest,
  TakeoverCompleteRequest,
  TakeoverEnterControlRequest,
  ViewportSizeResponse,
} from "./browser";

export type {
  FilterActionType,
  FilterOverrideActions,
  FilterSchema,
  FilterSchemaItem,
} from "./filters";

export type {
  CredentialStatus,
  ExtraCandidate,
  ExtraCredential,
  ExtraPlacement,
  LoginCredentialSpec,
  LoginFieldInfo,
  LoginFlowStatus,
  LoginFlowStatusEvent,
  LoginFormPayload,
  MatchHints,
  SiteStatusRequest,
} from "./login";

export type {
  ApprovalRequestEvent,
  HumanTakeoverRequestEvent,
  LoginFormDetectedEvent,
  RunEndEvent,
  RunErrorEvent,
  RunMetadataEvent,
  RunStartEvent,
  StreamRunEvent,
  StreamTruncatedEvent,
  TakeoverCancelledEvent,
  TakeoverStateChangeEvent,
  TextDeltaEvent,
  ToolCallRunEvent,
  ToolResultRunEvent,
  TraceEvent,
} from "./events";

export type {
  HistoryMatchSegment,
  HistorySearchMatch,
  HistorySearchResponse,
  HistorySearchResultItem,
} from "./history";

export type { UndoGroup, UndoListResponse } from "./undo";
