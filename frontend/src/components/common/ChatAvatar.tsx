import { Sparkles, User } from "lucide-react";

interface ChatAvatarProps {
  role: "user" | "assistant";
}

export default function ChatAvatar({ role }: ChatAvatarProps) {
  if (role === "assistant") {
    return (
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/15 mt-0.5">
        <Sparkles className="h-3.5 w-3.5 text-accent" />
      </div>
    );
  }

  return (
    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-default/50 mt-0.5">
      <User className="h-3.5 w-3.5" />
    </div>
  );
}
