import { vi } from "vitest";

/**
 * 为 `src/api/*` 端点测试统一桩掉全局 fetch。
 * 返回可断言的 `json` / `text` / `fetch` 三个 mock（默认 200 + 空对象响应）。
 */
export function stubFetch() {
  const json = vi.fn(() => Promise.resolve({}));
  const text = vi.fn(() => Promise.resolve(""));
  const fetchMock = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json, text }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return { json, text, fetch: fetchMock };
}
