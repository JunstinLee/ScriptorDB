import ChatInput from "./ChatInput";
import ChatMessages from "./ChatMessages";
import ModelProviderBar from "./ModelProviderBar";
import WelcomeScreen from "./WelcomeScreen";
import type { ChatMessage, Run } from "../types";

interface ChatPanelProps {
  activeSessionId: string | null;
  messages: ChatMessage[];
  runs: Run[];
  isLoading: boolean;
  settingsChanged: number;
  onSend: (prompt: string) => void;
  onNewSession: () => void;
  onHighlightRun: (runId: string) => void;
  onSelectionChange: (model: string, provider: string) => void;
}

export default function ChatPanel({
  activeSessionId,
  messages,
  runs,
  isLoading,
  settingsChanged,
  onSend,
  onNewSession,
  onHighlightRun,
  onSelectionChange,
}: ChatPanelProps) {
  if (!activeSessionId) {
    return <WelcomeScreen onNewSession={onNewSession} />;
  }

  return (
    <>
      <ChatMessages messages={messages} runs={runs} isLoading={isLoading} onHighlightRun={onHighlightRun} />
      <div className="absolute bottom-0 left-0 right-0 z-10 bg-background">
        <ModelProviderBar
          settingsChanged={settingsChanged}
          onSelectionChange={onSelectionChange}
        />
        <ChatInput onSend={onSend} disabled={isLoading} />
      </div>
    </>
  );
}
