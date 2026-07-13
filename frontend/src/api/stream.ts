import type { ChatRequest, StreamRunEvent } from "../types";
import { WorkspaceNotSelectedError } from "./core";

const BASE = "/api";

function processSseStream(
  res: Response,
  onEvent: (event: StreamRunEvent) => void,
  onError: (error: Error) => void,
  onDone: (fullOutput: string) => void,
  signal?: AbortSignal,
  onApprovalRequest?: (event: Extract<StreamRunEvent, { type: "approval_request" }>) => void,
): Promise<void> {
  return new Promise((resolve) => {
    void (async () => {
      try {
        const reader = res.body!.getReader();
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
                currentEvent === "error" ||
                currentEvent === "approval_request"
              ) {
                try {
                  const obj = JSON.parse(data) as StreamRunEvent;
                  console.log(
                    "[stream] SSE event: type=%s run_id=%s",
                    obj.type,
                    (obj as any).run_id ?? "-",
                  );
                  onEvent(obj);
                  if (obj.type === "metadata") {
                    doneCalled = true;
                    onDone(obj.full_output ?? "");
                  } else if (obj.type === "error") {
                    doneCalled = true;
                    onError(new Error(obj.message));
                  } else if (obj.type === "approval_request") {
                    onApprovalRequest?.(obj);
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
          if (signal?.aborted) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";
          processLines(lines);
        }

        buffer += decoder.decode();
        processLines(buffer.split("\n"));

        if (!signal?.aborted && !doneCalled) {
          onDone("");
        }
        resolve();
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          resolve();
          return;
        }
        onError(err instanceof Error ? err : new Error("Unknown error"));
        resolve();
      }
    })();
  });
}

export function streamChat(
  sessionId: string,
  body: ChatRequest,
  onEvent: (event: StreamRunEvent) => void,
  onError: (error: Error) => void,
  onDone: (fullOutput: string) => void,
  onApprovalRequest?: (event: Extract<StreamRunEvent, { type: "approval_request" }>) => void,
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

      await processSseStream(
        res,
        onEvent,
        onError,
        onDone,
        controller.signal,
        onApprovalRequest,
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      onError(err instanceof Error ? err : new Error("Unknown error"));
    }
  })();

  return controller;
}

export function streamApproval(
  sessionId: string,
  requestId: string,
  approvedMap: Record<string, boolean>,
  onEvent: (event: StreamRunEvent) => void,
  onError: (error: Error) => void,
  onDone: (fullOutput: string) => void,
  onApprovalRequest?: (event: Extract<StreamRunEvent, { type: "approval_request" }>) => void,
): AbortController {
  const controller = new AbortController();

  void (async () => {
    try {
      const res = await fetch(`${BASE}/sessions/${sessionId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: requestId, approved_map: approvedMap }),
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

      await processSseStream(
        res,
        onEvent,
        onError,
        onDone,
        controller.signal,
        onApprovalRequest,
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      onError(err instanceof Error ? err : new Error("Unknown error"));
    }
  })();

  return controller;
}
