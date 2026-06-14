import { useCallback, useState } from "react";

const SHOW_SESSION_ID_KEY = "scriptordb:show_session_id_hover";

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

  const setShowSessionIdHover = useCallback((value: boolean) => {
    try {
      localStorage.setItem(SHOW_SESSION_ID_KEY, String(value));
    } catch {
      // ignore quota / privacy errors
    }
    setShowSessionIdHoverState(value);
  }, []);

  return { showSessionIdHover, setShowSessionIdHover };
}
