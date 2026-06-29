import type { ChatRequest, StreamRunEvent } from "../types";
import { WorkspaceNotSelectedError } from "./core";

const BASE = "/api";

export function streamChat(
  sessionId: string,
  body: ChatRequest,
  onEvent: (event: StreamRunEvent) => void,
  onError: (error: Error) => void,
  onDone: (fullOutput: string) => void,
): AbortController {
  const controller = new AbortController();

  void (async () => {
    try {
      const res = await fetch(`${BASE}/sessions/${sessionId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        if (res.status === 409) {
          const text = await res.text().catch(() => "");
          if (text.includes("WORKSPACE_NOT_SELECTED")) {
            onError(new WorkspaceNotSelectedError(text));
            return;
          }
        }
        onError(new Error(`HTTP ${res.status}`));
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "message";
      let doneCalled = false;

      const processLines = (lines: string[]) => {
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") continue;
            if (
              currentEvent === "text_delta" ||
              currentEvent === "run_start" ||
              currentEvent === "run_end" ||
              currentEvent === "trace" ||
              currentEvent === "tool_call" ||
              currentEvent === "tool_result" ||
              currentEvent === "metadata" ||
              currentEvent === "error"
            ) {
              try {
                const obj = JSON.parse(data) as StreamRunEvent;
                onEvent(obj);
                if (obj.type === "metadata") {
                  doneCalled = true;
                  onDone(obj.full_output ?? "");
                } else if (obj.type === "error") {
                  doneCalled = true;
                  onError(new Error(obj.message));
                }
              } catch {
                // non-JSON data line, ignore
              }
            }
          } else if (line === "") {
            currentEvent = "message";
          }
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        processLines(lines);
      }

      buffer += decoder.decode();
      processLines(buffer.split("\n"));

      if (!controller.signal.aborted && !doneCalled) {
        onDone("");
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      onError(err instanceof Error ? err : new Error("Unknown error"));
    }
  })();

  return controller;
}
