import { Button } from "@heroui/react";
import { Database, MessageSquarePlus, Sparkles } from "lucide-react";

interface WelcomeScreenProps {
  onNewSession: () => void;
}

export default function WelcomeScreen({ onNewSession }: WelcomeScreenProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 text-center">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-accent/15 p-3">
          <Database className="h-8 w-8 text-accent" />
        </div>
        <h1 className="text-3xl font-bold">ScriptorDB</h1>
      </div>
      <p className="max-w-md text-muted">
        AI-powered database operator. Ask questions in natural language,
        run queries, and explore your database schema.
      </p>
      <div className="flex gap-3">
        <Button variant="primary" onPress={onNewSession}>
          <MessageSquarePlus className="mr-2 h-4 w-4" />
          New Session
        </Button>
      </div>
      <div className="mt-8 grid max-w-lg grid-cols-3 gap-4 text-left">
        <div className="rounded-xl border p-4">
          <Sparkles className="mb-2 h-5 w-5 text-accent" />
          <h3 className="text-sm font-semibold">Natural Language</h3>
          <p className="mt-1 text-xs text-muted">
            Describe what you want in plain English
          </p>
        </div>
        <div className="rounded-xl border p-4">
          <Database className="mb-2 h-5 w-5 text-accent" />
          <h3 className="text-sm font-semibold">Query & Modify</h3>
          <p className="mt-1 text-xs text-muted">
            SELECT, INSERT, UPDATE via AI agent
          </p>
        </div>
        <div className="rounded-xl border p-4">
          <svg
            className="mb-2 h-5 w-5 text-accent"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            viewBox="0 0 24 24"
          >
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
          </svg>
          <h3 className="text-sm font-semibold">Multi-Provider</h3>
          <p className="mt-1 text-xs text-muted">
            OpenAI, Anthropic, Google, Groq & more
          </p>
        </div>
      </div>
    </div>
  );
}
