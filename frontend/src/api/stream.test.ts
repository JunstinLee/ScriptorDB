import { describe, expect, it, vi } from "vitest";
import { streamChat } from "./stream";

function createSSEResponse(chunks: string[]): Response {
  return new Response(
    new ReadableStream({
      start(controller) {
        const encoder = new TextEncoder();
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    }),
    { status: 200 },
  );
}

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockClear();
});

describe("streamChat", () => {
  it("sends POST with correct payload", () => {
    mockFetch.mockResolvedValueOnce(
      createSSEResponse([
        'event: metadata\ndata: {"type":"metadata","run_id":"r1","full_output":""}\n\n',
      ]),
    );

    streamChat(
      "session-1",
      { prompt: "hello", model: "gpt-4", provider: "openai" },
      () => {},
      () => {},
      () => {},
    );

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/sessions/session-1/chat",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: "hello",
          model: "gpt-4",
          provider: "openai",
        }),
        signal: expect.any(AbortSignal),
      },
    );
  });

  it("calls onEvent for text_delta events", async () => {
    const onEvent = vi.fn();
    const onDone = vi.fn();

    mockFetch.mockResolvedValueOnce(
      createSSEResponse([
        'event: text_delta\ndata: {"type":"text_delta","run_id":"r1","delta":"Hello"}\n\n',
        'event: text_delta\ndata: {"type":"text_delta","run_id":"r1","delta":" world"}\n\n',
        'event: metadata\ndata: {"type":"metadata","run_id":"r1","full_output":"Hello world"}\n\n',
      ]),
    );

    streamChat("s1", { prompt: "hi" }, onEvent, vi.fn(), onDone);

    await vi.waitFor(
      () => {
        expect(onDone).toHaveBeenCalled();
      },
      { timeout: 500 },
    );

    const textDeltas = onEvent.mock.calls
      .map((c: any[]) => c[0])
      .filter((e: any) => e.type === "text_delta");
    expect(textDeltas).toHaveLength(2);
    expect(textDeltas[0].delta).toBe("Hello");
    expect(textDeltas[1].delta).toBe(" world");
  });

  it("skips [DONE] data lines", async () => {
    const onEvent = vi.fn();
    const onDone = vi.fn();

    mockFetch.mockResolvedValueOnce(
      createSSEResponse([
        'event: text_delta\ndata: {"type":"text_delta","run_id":"r1","delta":"hi"}\n\n',
        "data: [DONE]\n\n",
        'event: text_delta\ndata: {"type":"text_delta","run_id":"r1","delta":"after"}\n\n',
        'event: metadata\ndata: {"type":"metadata","run_id":"r1","full_output":"hiafter"}\n\n',
      ]),
    );

    streamChat("s1", { prompt: "hi" }, onEvent, vi.fn(), onDone);

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 500 });

    const textDeltas = onEvent.mock.calls
      .map((c: any[]) => c[0])
      .filter((e: any) => e.type === "text_delta");
    expect(textDeltas).toHaveLength(2);
    expect(textDeltas[0].delta).toBe("hi");
    expect(textDeltas[1].delta).toBe("after");
  });

  it("calls onDone with parsed full_output from metadata", async () => {
    const onDone = vi.fn();

    mockFetch.mockResolvedValueOnce(
      createSSEResponse([
        'event: metadata\ndata: {"type":"metadata","run_id":"r1","full_output":"Complete response"}\n\n',
      ]),
    );

    streamChat("s1", { prompt: "hi" }, vi.fn(), vi.fn(), onDone);

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 500 });
    expect(onDone).toHaveBeenCalledWith("Complete response");
  });

  it("calls onDone with empty string when no metadata", async () => {
    const onDone = vi.fn();

    mockFetch.mockResolvedValueOnce(
      createSSEResponse(["event: text_delta\ndata: {\"type\":\"text_delta\",\"run_id\":\"r1\",\"delta\":\"text\"}\n\n"]),
    );

    streamChat("s1", { prompt: "hi" }, vi.fn(), vi.fn(), onDone);

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 500 });
    expect(onDone).toHaveBeenCalledWith("");
  });

  it("calls onError for error events", async () => {
    const onError = vi.fn();
    const onDone = vi.fn();

    mockFetch.mockResolvedValueOnce(
      createSSEResponse([
        'event: error\ndata: {"type":"error","message":"Something went wrong"}\n\n',
        'event: metadata\ndata: {"type":"metadata","run_id":"r1","full_output":""}\n\n',
      ]),
    );

    streamChat("s1", { prompt: "hi" }, vi.fn(), onError, onDone);

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 500 });
    expect(onError).toHaveBeenCalledWith("Something went wrong");
  });

  it("calls onError when response is not ok", async () => {
    const onError = vi.fn();

    mockFetch.mockResolvedValueOnce(
      new Response(null, { status: 500 }),
    );

    streamChat("s1", { prompt: "hi" }, vi.fn(), onError, vi.fn());

    await vi.waitFor(() => expect(onError).toHaveBeenCalled(), { timeout: 500 });
    expect(onError).toHaveBeenCalledWith("HTTP 500");
  });

  it("calls onError on network failure", async () => {
    const onError = vi.fn();

    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    streamChat("s1", { prompt: "hi" }, vi.fn(), onError, vi.fn());

    await vi.waitFor(() => expect(onError).toHaveBeenCalled(), { timeout: 500 });
    expect(onError).toHaveBeenCalledWith("Network error");
  });

  it("returns AbortController and ignores AbortError", async () => {
    const onError = vi.fn();
    const onDone = vi.fn();

    const abortError = new DOMException("The user aborted a request.", "AbortError");

    mockFetch.mockRejectedValueOnce(abortError);

    const controller = streamChat("s1", { prompt: "hi" }, vi.fn(), onError, onDone);

    expect(controller).toBeInstanceOf(AbortController);

    await vi.waitFor(
      () => {
        expect(mockFetch).toHaveBeenCalled();
      },
      { timeout: 500 },
    );

    expect(onError).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
  });

  it("handles tool_call and tool_result events", async () => {
    const onEvent = vi.fn();
    const onDone = vi.fn();

    mockFetch.mockResolvedValueOnce(
      createSSEResponse([
        'event: tool_call\ndata: {"type":"tool_call","run_id":"r1","call_id":"c1","tool_name":"get_schema","args":{},"timestamp":"2024-01-01T00:00:00Z"}\n\n',
        'event: tool_result\ndata: {"type":"tool_result","run_id":"r1","call_id":"c1","tool_name":"get_schema","success":true,"output":"3 tables","duration_ms":12}\n\n',
        'event: metadata\ndata: {"type":"metadata","run_id":"r1","full_output":"done"}\n\n',
      ]),
    );

    streamChat("s1", { prompt: "hi" }, onEvent, vi.fn(), onDone);

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 500 });

    const toolCallEvt = onEvent.mock.calls
      .map((c: any[]) => c[0])
      .find((e: any) => e.type === "tool_call");
    expect(toolCallEvt).toBeDefined();
    expect(toolCallEvt.tool_name).toBe("get_schema");

    const toolResultEvt = onEvent.mock.calls
      .map((c: any[]) => c[0])
      .find((e: any) => e.type === "tool_result");
    expect(toolResultEvt).toBeDefined();
    expect(toolResultEvt.success).toBe(true);
  });

  it("handles malformed JSON in event data gracefully", async () => {
    const onDone = vi.fn();

    mockFetch.mockResolvedValueOnce(
      createSSEResponse([
        "event: text_delta\ndata: not-valid-json\n\n",
        'event: metadata\ndata: {"type":"metadata","run_id":"r1","full_output":"ok"}\n\n',
      ]),
    );

    streamChat("s1", { prompt: "hi" }, vi.fn(), vi.fn(), onDone);

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 500 });
    expect(onDone).toHaveBeenCalledWith("ok");
  });
});
