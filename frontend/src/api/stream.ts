import type { ChatRequest, StreamRunEvent } from "../types";
import { WorkspaceNotSelectedError } from "./core";

const BASE = "/api";

/** 已识别的事件类型白名单（与 types/events.ts 的 StreamRunEvent union 同步） */
const KNOWN_EVENT_TYPES: Record<string, true> = {
  text_delta: true,
  run_start: true,
  run_end: true,
  trace: true,
  tool_call: true,
  tool_result: true,
  metadata: true,
  error: true,
  approval_request: true,
  browser_action: true,
  login_form_detected: true,
  human_takeover_request: true,
  takeover_state_change: true,
  takeover_cancelled: true,
  stream_truncated: true,
  login_flow_status: true,
};

export interface SseStreamCallbacks {
  onEvent: (event: StreamRunEvent) => void;
  onError: (error: Error) => void;
  /** 仅在收到终态事件（metadata / error）时调用，断连不再视为正常收尾 */
  onDone: (fullOutput: string) => void;
  /** 流结束时未收到终态事件：调用方需按 lastEventId 重挂 */
  onDetached: (lastEventId: number) => void;
  onApprovalRequest?: (
    event: Extract<StreamRunEvent, { type: "approval_request" }>,
  ) => void;
}

export function processSseStream(
  res: Response,
  callbacks: SseStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const { onEvent, onError, onDone, onDetached, onApprovalRequest } = callbacks;

  return new Promise((resolve) => {
    void (async () => {
      try {
        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let currentEvent = "message";
        let lastEventId = 0;
        let doneCalled = false;

        const processLines = (lines: string[]) => {
          for (const line of lines) {
            if (line.startsWith("id: ")) {
              const parsed = Number.parseInt(line.slice(4).trim(), 10);
              if (!Number.isNaN(parsed)) lastEventId = parsed;
            } else if (line.startsWith("event: ")) {
              currentEvent = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              const data = line.slice(6);
              if (data === "[DONE]") continue;
              if (KNOWN_EVENT_TYPES[currentEvent]) {
                try {
                  const obj = JSON.parse(data) as StreamRunEvent;
                  console.log(
                    "[stream] SSE event: type=%s run_id=%s id=%d",
                    obj.type,
                    obj.run_id ?? "-",
                    lastEventId,
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
                  } else if (obj.type === "stream_truncated") {
                    console.warn(
                      "[stream] stream_truncated dropped_before=%d",
                      obj.dropped_before,
                    );
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

        // 只有终态事件才算正常收尾；流结束而未收终态 = 断连，交给调用方重挂
        if (!signal?.aborted && !doneCalled) {
          onDetached(lastEventId);
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

async function consumeSse(
  url: string,
  init: RequestInit,
  controller: AbortController,
  callbacks: SseStreamCallbacks,
): Promise<void> {
  try {
    const res = await fetch(url, { ...init, signal: controller.signal });

    if (!res.ok || !res.body) {
      if (res.status === 409) {
        const text = await res.text().catch(() => "");
        if (text.includes("WORKSPACE_NOT_SELECTED")) {
          callbacks.onError(new WorkspaceNotSelectedError(text));
          return;
        }
      }
      callbacks.onError(new Error(`HTTP ${res.status}`));
      return;
    }

    await processSseStream(res, callbacks, controller.signal);
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return;
    callbacks.onError(err instanceof Error ? err : new Error("Unknown error"));
  }
}

export function streamChat(
  sessionId: string,
  body: ChatRequest,
  callbacks: SseStreamCallbacks,
): AbortController {
  const controller = new AbortController();
  void consumeSse(
    `${BASE}/sessions/${sessionId}/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    controller,
    callbacks,
  );
  return controller;
}

/** 重挂活动 run 的流：按游标增量重放（GET 语义，无副作用）。 */
export function attachSessionStream(
  sessionId: string,
  fromIndex: number,
  callbacks: SseStreamCallbacks,
): AbortController {
  const controller = new AbortController();
  void consumeSse(
    `${BASE}/sessions/${sessionId}/stream?from_index=${fromIndex}`,
    { method: "GET" },
    controller,
    callbacks,
  );
  return controller;
}
