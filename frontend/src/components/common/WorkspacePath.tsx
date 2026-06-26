import { useEffect, useRef, useState } from "react";
import { formatWorkspacePath } from "../../utils/workspace";

interface WorkspacePathProps {
  path: string | null | undefined;
  className?: string;
  fallback?: string;
  compact?: boolean;
}

export default function WorkspacePath({
  path,
  className = "",
  fallback = "—",
  compact = false,
}: WorkspacePathProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const textRef = useRef<HTMLSpanElement | null>(null);
  const [overflow, setOverflow] = useState(false);
  const [paused, setPaused] = useState(false);

  const display = formatWorkspacePath(path) || (path ? path : fallback);

  useEffect(() => {
    if (compact) return;
    const container = containerRef.current;
    const text = textRef.current;
    if (!container || !text) return;

    const measure = () => {
      setOverflow(text.scrollWidth > container.clientWidth + 1);
    };

    measure();

    const observer = new ResizeObserver(measure);
    observer.observe(container);
    observer.observe(text);

    return () => observer.disconnect();
  }, [display, compact]);

  if (compact) {
    return (
      <div
        ref={containerRef}
        className={`block min-w-0 w-full truncate ${className}`}
        title={display || undefined}
      >
        <span ref={textRef} className="block truncate">
          {display}
        </span>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`relative min-w-0 overflow-hidden ${className}`}
      title={display || undefined}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div
        className={
          overflow
            ? `flex w-max items-center gap-8 ${paused ? "" : "workspace-path-marquee"}`
            : "truncate"
        }
      >
        <span
          ref={textRef}
          className="whitespace-nowrap"
        >
          {display}
        </span>
        {overflow && <span className="whitespace-nowrap">{display}</span>}
      </div>
    </div>
  );
}
