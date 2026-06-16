import ChatInput from "./ChatInput";
import ChatMessages from "./ChatMessages";
import WelcomeScreen from "./WelcomeScreen";
import type { ChatMessage, Run } from "../types";

interface ChatPanelProps {
  activeSessionId: string | null;
  messages: ChatMessage[];
  runs: Run[];
  isLoading: boolean;
  onSend: (prompt: string) => void;
  onNewSession: () => void;
}

export default function ChatPanel({
  activeSessionId,
  messages,
  runs,
  isLoading,
  onSend,
  onNewSession,
}: ChatPanelProps) {
  if (!activeSessionId) {
    return <WelcomeScreen onNewSession={onNewSession} />;
  }

  return (
    <>
      <ChatMessages messages={messages} runs={runs} isLoading={isLoading} />
      <div className="absolute bottom-0 left-0 right-0 z-10 bg-background">
        <ChatInput onSend={onSend} disabled={isLoading} />
      </div>
    </>
  );
}
