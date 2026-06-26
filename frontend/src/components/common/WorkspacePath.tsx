import { formatWorkspacePath } from "../../utils/workspace";

interface WorkspacePathProps {
  path: string | null | undefined;
  className?: string;
  fallback?: string;
}

export default function WorkspacePath({
  path,
  className = "",
  fallback = "—",
}: WorkspacePathProps) {
  const display = formatWorkspacePath(path) || (path ? path : fallback);

  return (
    <div
      className={`block min-w-0 w-full truncate ${className}`}
      title={display || undefined}
    >
      <span className="block truncate">{display}</span>
    </div>
  );
}
