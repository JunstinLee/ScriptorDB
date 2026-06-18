import { useCallback, useState } from "react";

const SHOW_SESSION_ID_KEY = "scriptordb:show_session_id_hover";
const SHOW_SCHEMA_SQL_KEY = "scriptordb:show_schema_sql";

export function useAppSettings() {
  const [showSessionIdHover, setShowSessionIdHoverState] = useState<boolean>(
    () => {
      try {
        return localStorage.getItem(SHOW_SESSION_ID_KEY) === "true";
      } catch {
        return false;
      }
    },
  );

  const [showSchemaSql, setShowSchemaSqlState] = useState<boolean>(() => {
    try {
      return localStorage.getItem(SHOW_SCHEMA_SQL_KEY) === "true";
    } catch {
      return false;
    }
  });

  const setShowSessionIdHover = useCallback((value: boolean) => {
    try {
      localStorage.setItem(SHOW_SESSION_ID_KEY, String(value));
    } catch {
      // ignore quota / privacy errors
    }
    setShowSessionIdHoverState(value);
  }, []);

  const setShowSchemaSql = useCallback((value: boolean) => {
    try {
      localStorage.setItem(SHOW_SCHEMA_SQL_KEY, String(value));
    } catch {
      // ignore quota / privacy errors
    }
    setShowSchemaSqlState(value);
  }, []);

  return { showSessionIdHover, setShowSessionIdHover, showSchemaSql, setShowSchemaSql };
}
