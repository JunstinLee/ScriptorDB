import { useCallback, useState } from "react";

const SHOW_SESSION_ID_KEY = "scriptordb:show_session_id_hover";
const SHOW_SCHEMA_SQL_KEY = "scriptordb:show_schema_sql";
const ACTIVE_WORKSPACE_ID_KEY = "scriptordb:active_workspace_id";

function readStoredFlag(key: string): boolean {
  try {
    return localStorage.getItem(key) === "true";
  } catch {
    return false;
  }
}

function readStoredString(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStoredFlag(key: string, value: boolean): void {
  try {
    localStorage.setItem(key, String(value));
  } catch {
    // ignore quota / privacy errors
  }
}

function writeStoredString(key: string, value: string | null): void {
  try {
    if (value) {
      localStorage.setItem(key, value);
    } else {
      localStorage.removeItem(key);
    }
  } catch {
    // ignore quota / privacy errors
  }
}

export function readActiveWorkspaceId(): string | null {
  return readStoredString(ACTIVE_WORKSPACE_ID_KEY);
}

export function writeActiveWorkspaceId(id: string | null): void {
  writeStoredString(ACTIVE_WORKSPACE_ID_KEY, id);
}

export function useAppSettings() {
  const [showSessionIdHover, setShowSessionIdHoverState] = useState<boolean>(
    () => readStoredFlag(SHOW_SESSION_ID_KEY),
  );

  const [showSchemaSql, setShowSchemaSqlState] = useState<boolean>(() =>
    readStoredFlag(SHOW_SCHEMA_SQL_KEY),
  );

  const [activeWorkspaceId, setActiveWorkspaceIdState] = useState<string | null>(
    () => readActiveWorkspaceId(),
  );

  const setShowSessionIdHover = useCallback((value: boolean) => {
    writeStoredFlag(SHOW_SESSION_ID_KEY, value);
    setShowSessionIdHoverState(value);
  }, []);

  const setShowSchemaSql = useCallback((value: boolean) => {
    writeStoredFlag(SHOW_SCHEMA_SQL_KEY, value);
    setShowSchemaSqlState(value);
  }, []);

  const setActiveWorkspaceId = useCallback((id: string | null) => {
    writeActiveWorkspaceId(id);
    setActiveWorkspaceIdState(id);
  }, []);

  return {
    showSessionIdHover,
    setShowSessionIdHover,
    showSchemaSql,
    setShowSchemaSql,
    activeWorkspaceId,
    setActiveWorkspaceId,
  };
}
