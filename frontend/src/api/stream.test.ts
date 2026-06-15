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
        "event: metadata\ndata: {}\n\n",
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

  it("calls onText for message events", async () => {
    const onText = vi.fn();
    const onDone = vi.fn();

    mockFetch.mockResolvedValueOnce(
      createSSEResponse([
        "event: message\ndata: Hello\n\n",
        "event: message\ndata:  world\n\n",
        "event: metadata\ndata: {}\n\n",
      ]),
    );

    streamChat("s1", { prompt: "hi" }, onText, vi.fn(), onDone);

    await vi.waitFor(
      () => {
        expect(onDone).toHaveBeenCalled();
      },
      { timeout: 500 },
    );

    expect(onText).toHaveBeenCalledWith("Hello");
    expect(onText).toHaveBeenCalledWith(" world");
    expect(onText).toHaveBeenCalledTimes(2);
  });

  it("skips [DONE] data lines", async () => {
    const onText = vi.fn();
    const onDone = vi.fn();

    mockFetch.mockResolvedValueOnce(
      createSSEResponse([
        "event: message\ndata: hi\n\n",
        "event: message\ndata: [DONE]\n\n",
        "event: message\ndata: after\n\n",
        "event: metadata\ndata: {}\n\n",
      ]),
    );

    streamChat("s1", { prompt: "hi" }, onText, vi.fn(), onDone);

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 500 });

    expect(onText).toHaveBeenCalledWith("hi");
    expect(onText).toHaveBeenCalledWith("after");
    expect(onText).toHaveBeenCalledTimes(2);
  });

  it("calls onDone with parsed full_output from metadata", async () => {
    const onDone = vi.fn();

    mockFetch.mockResolvedValueOnce(
      createSSEResponse([
        "event: metadata\ndata: {\"full_output\":\"Complete response\"}\n\n",
      ]),
    );

    streamChat("s1", { prompt: "hi" }, vi.fn(), vi.fn(), onDone);

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 500 });
    expect(onDone).toHaveBeenCalledWith("Complete response");
  });

  it("calls onDone with empty string when no metadata", async () => {
    const onDone = vi.fn();

    mockFetch.mockResolvedValueOnce(
      createSSEResponse(["event: message\ndata: text\n\n"]),
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
        "event: error\ndata: Something went wrong\n\n",
        "event: metadata\ndata: {}\n\n",
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

    // AbortError should NOT trigger onError
    expect(onError).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
  });

  it("handles empty line to reset event type", async () => {
    const onError = vi.fn();
    const onDone = vi.fn();

    mockFetch.mockResolvedValueOnce(
      createSSEResponse([
        "event: error\ndata: err1\n\n",
        "\n",
        "data: this is message event after reset\n\n",
        "event: metadata\ndata: {}\n\n",
      ]),
    );

    streamChat("s1", { prompt: "hi" }, vi.fn(), onError, onDone);

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 500 });
    expect(onError).toHaveBeenCalledWith("err1");
  });

  it("handles malformed metadata JSON gracefully", async () => {
    const onDone = vi.fn();

    mockFetch.mockResolvedValueOnce(
      createSSEResponse([
        "event: metadata\ndata: not-valid-json\n\n",
      ]),
    );

    streamChat("s1", { prompt: "hi" }, vi.fn(), vi.fn(), onDone);

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled(), { timeout: 500 });
    expect(onDone).toHaveBeenCalledWith("");
  });
});
