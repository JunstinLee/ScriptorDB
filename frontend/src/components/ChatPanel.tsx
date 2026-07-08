import ChatInput from "./ChatInput";
import ChatMessages from "./ChatMessages";
import ModelProviderBar from "./ModelProviderBar";
import WelcomeScreen from "./WelcomeScreen";
import type { ChatMessage, Run, SchemaTable, UndoGroup, WorkspaceDetail } from "../types";

interface ChatPanelProps {
  activeSessionId: string | null;
  messages: ChatMessage[];
  runs: Run[];
  isLoading: boolean;
  settingsChanged: number;
  workspace: WorkspaceDetail | null;
  tables: SchemaTable[];
  undoGroups: UndoGroup[];
  onSend: (prompt: string, attachments: string[]) => void;
  onNewSession: () => void;
  onRevertToHere: (groupId: number) => void;
  onHighlightRun: (runId: string) => void;
  onSelectionChange: (model: string, provider: string) => void;
}

export default function ChatPanel({
  activeSessionId,
  messages,
  runs,
  isLoading,
  settingsChanged,
  workspace,
  tables,
  undoGroups,
  onSend,
  onNewSession,
  onRevertToHere,
  onHighlightRun,
  onSelectionChange,
}: ChatPanelProps) {
  return (
    <div className="flex flex-1 flex-col min-h-0">
      <div className="flex-1 overflow-y-auto min-h-0">
        {activeSessionId ? (
          <ChatMessages
            messages={messages}
            runs={runs}
            isLoading={isLoading}
            undoGroups={undoGroups}
            onRevertToHere={onRevertToHere}
            onHighlightRun={onHighlightRun}
          />
        ) : (
          <WelcomeScreen
            workspace={workspace}
            tables={tables}
            onNewSession={onNewSession}
          />
        )}
      </div>

      <div className="shrink-0 bg-background px-4 py-3">
        <div className="overflow-hidden rounded-2xl border border-grid bg-surface">
          <ChatInput onSend={onSend} disabled={isLoading} />
          <ModelProviderBar
            settingsChanged={settingsChanged}
            onSelectionChange={onSelectionChange}
          />
        </div>
      </div>
    </div>
  );
}
