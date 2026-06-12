import { useCallback, useRef } from "react";
import ChatHeader from "./components/ChatHeader";
import ChatInput from "./components/ChatInput";
import ChatMessages from "./components/ChatMessages";
import Sidebar from "./components/Sidebar";
import WelcomeScreen from "./components/WelcomeScreen";
import { useSchema } from "./hooks/useSchema";
import { useSessions } from "./hooks/useSessions";
import { streamChat } from "./api/client";

export default function App() {
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
  } = useSessions();

  const { tables, loading: schemaLoading } = useSchema();
  const abortRef = useRef<AbortController | null>(null);

  const handleNewSession = useCallback(() => {
    void createNewSession();
  }, [createNewSession]);

  const handleSend = useCallback(
    (prompt: string, model?: string | null, provider?: string | null) => {
      let sessionId = activeSessionId;

      const sendToSession = (sid: string) => {
        addUserMessage(prompt);
        setLoading(true);

        abortRef.current = streamChat(
          sid,
          { prompt, model, provider },
          (delta) => {
            appendStreamingText(delta);
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
      appendStreamingText,
      createNewSession,
      finalizeAssistantMessage,
      setLoading,
    ],
  );

  const handleDeleteSession = useCallback(
    (id: string) => {
      void removeSession(id);
    },
    [removeSession],
  );

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
      />

      <div className="flex flex-1 flex-col min-w-0">
        <ChatHeader activeSessionId={activeSessionId} />

        <div className="flex flex-1 flex-col min-h-0 relative">
          {activeSessionId ? (
            <>
              <ChatMessages messages={messages} isLoading={isLoading} />
              <div className="absolute bottom-0 left-0 right-0 z-10 bg-background">
                <ChatInput onSend={handleSend} disabled={isLoading} />
              </div>
            </>
          ) : (
            <WelcomeScreen onNewSession={handleNewSession} />
          )}
        </div>
      </div>
    </div>
  );
}
