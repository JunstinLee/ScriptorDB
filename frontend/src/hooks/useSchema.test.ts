import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useSchema } from "./useSchema";
import * as client from "../api/client";

const mockGetSchema = vi.fn();

beforeEach(() => {
  vi.spyOn(client, "getSchema").mockImplementation(mockGetSchema);
  mockGetSchema.mockClear();
});

describe("useSchema", () => {
  it("fetches tables on mount", async () => {
    mockGetSchema.mockResolvedValueOnce({
      tables: [
        { name: "users", sql: "CREATE TABLE users (id INTEGER)" },
      ],
    });

    const { result } = renderHook(() => useSchema());

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.tables).toEqual([
      { name: "users", sql: "CREATE TABLE users (id INTEGER)" },
    ]);
  });

  it("sets empty tables on fetch error", async () => {
    mockGetSchema.mockRejectedValueOnce(new Error("network error"));

    const { result } = renderHook(() => useSchema());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.tables).toEqual([]);
  });

  it("refresh calls fetchSchema again", async () => {
    mockGetSchema
      .mockResolvedValueOnce({ tables: [{ name: "t1", sql: "..." }] })
      .mockResolvedValueOnce({ tables: [{ name: "t2", sql: "..." }] });

    const { result } = renderHook(() => useSchema());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.tables).toEqual([{ name: "t1", sql: "..." }]);

    await result.current.refresh();

    await waitFor(() => {
      expect(result.current.tables).toEqual([{ name: "t2", sql: "..." }]);
    });
  });
});
