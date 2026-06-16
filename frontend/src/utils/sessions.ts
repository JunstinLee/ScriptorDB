import { getSession } from "../api/client";
import type { ChatMessage, Run, SessionListItem } from "../types";

export const TITLE_MAX_LEN = 24;
export const DEFAULT_TITLE = "New Chat";
export const ACTIVE_SESSION_KEY = "scriptordb:active_session_id";

export interface SessionMeta {
  session_id: string;
  created_at: string;
  title: string;
}

export function deriveTitle(messages: { role: string; content: string }[]): string {
  const firstUser = messages.find((m) => m.role === "user" && m.content.trim());
  if (!firstUser) return DEFAULT_TITLE;
  const cleaned = firstUser.content.replace(/\s+/g, " ").trim();
  return cleaned.length > TITLE_MAX_LEN ? `${cleaned.slice(0, TITLE_MAX_LEN)}…` : cleaned;
}

export function metaFromListItem(item: SessionListItem, fallbackTitle: string): SessionMeta {
  return {
    session_id: item.session_id,
    created_at: item.created_at,
    title: item.title || fallbackTitle,
  };
}

export async function loadSessionMessages(sessionId: string): Promise<ChatMessage[]> {
  const info = await getSession(sessionId);
  return info.messages.map((m) => ({
    role: m.role,
    content: m.content,
    timestamp: m.timestamp,
  }));
}

export async function loadSessionData(
  sessionId: string,
): Promise<{ messages: ChatMessage[]; runs: Run[] }> {
  const info = await getSession(sessionId);
  const messages = info.messages.map((m) => ({
    role: m.role,
    content: m.content,
    timestamp: m.timestamp,
  }));
  const runs: Run[] = (info.runs ?? []).map((run) => ({
    ...run,
    tool_invocations: run.tool_invocations ?? [],
    trace_steps: run.trace_steps ?? [],
    final_output: run.final_output ?? "",
  }));
  return { messages, runs };
}

export async function loadSessionTitle(sessionId: string): Promise<string> {
  const info = await getSession(sessionId);
  return deriveTitle(info.messages);
}

export function readStoredActiveSession(): string | null {
  try {
    return localStorage.getItem(ACTIVE_SESSION_KEY);
  } catch {
    return null;
  }
}

export function writeStoredActiveSession(id: string | null): void {
  try {
    if (id) {
      localStorage.setItem(ACTIVE_SESSION_KEY, id);
    } else {
      localStorage.removeItem(ACTIVE_SESSION_KEY);
    }
  } catch {
    // ignore quota / privacy mode errors
  }
}
