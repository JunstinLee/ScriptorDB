// Backward-compatible re-export hub — split into domain modules:
//   core.ts   — request base function
//   sessions.ts — session CRUD + schema
//   stream.ts   — SSE streaming chat
//   models.ts   — model listing / canonical APIs
//   settings.ts — settings + API key management

export { type SessionInfo } from "./sessions";
export {
  createSession,
  listSessions,
  getSession,
  deleteSession,
  getSchema,
} from "./sessions";
export { streamChat } from "./stream";
export {
  health,
  fetchModels,
  fetchRecommendedModels,
  fetchDefaultModel,
  fetchCanonicalModels,
  fetchModelsWithCanonical,
} from "./models";
export {
  fetchSettings,
  updateSettings,
  saveApiKey,
  deleteApiKey,
  testApiKey,
} from "./settings";
