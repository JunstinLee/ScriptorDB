import { useCallback, useMemo, useRef, useState } from "react";
import ChatHeader from "./components/ChatHeader";
import ChatPanel from "./components/ChatPanel";
import SettingsModal from "./components/SettingsModal";
import Sidebar from "./components/Sidebar";
import { useAppSettings } from "./hooks/useAppSettings";
import { useSchema } from "./hooks/useSchema";
import { useSessions } from "./hooks/useSessions";
import { useRuns } from "./hooks/useRuns";
import { streamChat } from "./api/client";
import { useOverlayState } from "@heroui/react";
import type { Run } from "./types";

export default function App() {
  const { getRuns, appendEvent, setRuns } = useRuns();

  const handleRunsLoaded = useCallback(
    (_sessionId: string, loadedRuns: Run[]) => {
      setRuns(_sessionId, loadedRuns);
    },
    [setRuns],
  );

  const {
    sessions,
    activeSessionId,
    messages,
    isLoading,
    createNewSession,
    removeSession,
    switchSession,
    addUserMessage,
    appendStreamingText,
    finalizeAssistantMessage,
    setLoading,
    refreshSessionTitle,
    refreshSessions,
  } = useSessions(handleRunsLoaded);

  const runs = activeSessionId ? getRuns(activeSessionId) : [];

  const { tables, loading: schemaLoading } = useSchema();
  const abortRef = useRef<AbortController | null>(null);
  const settingsModal = useOverlayState();
  const [settingsChanged, setSettingsChanged] = useState(0);
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedProvider, setSelectedProvider] = useState("");
  const { showSessionIdHover, setShowSessionIdHover } = useAppSettings();

  const activeSessionTitle = useMemo(
    () => sessions.find((s) => s.session_id === activeSessionId)?.title ?? null,
    [sessions, activeSessionId],
  );

  const handleNewSession = useCallback(() => {
    void createNewSession();
  }, [createNewSession]);

  const handleSend = useCallback(
    (prompt: string) => {
      const sessionId = activeSessionId;

      const sendToSession = (sid: string) => {
        addUserMessage(prompt);
        setLoading(true);

        abortRef.current = streamChat(
          sid,
          { prompt, model: selectedModel || null, provider: selectedProvider || null },
          (event) => {
            appendEvent(sid, event);
            if (event.type === "text_delta") {
              appendStreamingText(event.delta);
            }
          },
          (error) => {
            appendStreamingText(`\n\nError: ${error}`);
            setLoading(false);
          },
          (fullOutput) => {
            finalizeAssistantMessage(fullOutput);
            setLoading(false);
            void refreshSessionTitle(sid);
          },
        );
      };

      if (!sessionId) {
        void (async () => {
          const sid = await createNewSession();
          if (sid) {
            sendToSession(sid);
          }
        })();
      } else {
        sendToSession(sessionId);
      }
    },
    [
      activeSessionId,
      addUserMessage,
      appendEvent,
      appendStreamingText,
      createNewSession,
      finalizeAssistantMessage,
      refreshSessionTitle,
      setLoading,
      selectedModel,
      selectedProvider,
    ],
  );

  const handleDeleteSession = useCallback(
    (id: string) => {
      void removeSession(id);
    },
    [removeSession],
  );

  const handleOpenSettings = useCallback(() => {
    settingsModal.open();
  }, [settingsModal]);

  return (
    <div className="flex h-screen bg-background text-foreground">
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        tables={tables}
        schemaLoading={schemaLoading}
        onNewSession={handleNewSession}
        onSwitchSession={switchSession}
        onDeleteSession={handleDeleteSession}
        onOpenSettings={handleOpenSettings}
        showSessionIdHover={showSessionIdHover}
      />

      <div className="flex flex-1 flex-col min-w-0">
        <ChatHeader
          activeSessionId={activeSessionId}
          activeSessionTitle={activeSessionTitle}
          showSessionIdHover={showSessionIdHover}
          settingsChanged={settingsChanged}
          onSelectionChange={(model, provider) => {
            setSelectedModel(model);
            setSelectedProvider(provider);
          }}
        />

        <div className="flex flex-1 flex-col min-h-0 relative">
          <ChatPanel
            activeSessionId={activeSessionId}
            messages={messages}
            runs={runs}
            isLoading={isLoading}
            onSend={handleSend}
            onNewSession={handleNewSession}
          />
        </div>
      </div>

      <SettingsModal
        isOpen={settingsModal.isOpen}
        onOpenChange={(open) => {
          if (open) settingsModal.open();
          else {
            settingsModal.close();
            setSettingsChanged((v) => v + 1);
          }
        }}
        onSessionsChanged={() => void refreshSessions()}
        showSessionIdHover={showSessionIdHover}
        setShowSessionIdHover={setShowSessionIdHover}
      />
    </div>
  );
}
