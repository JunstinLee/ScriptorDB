import { describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAppSettings } from "./useAppSettings";

describe("useAppSettings", () => {
  it("defaults showSessionIdHover to false", () => {
    const { result } = renderHook(() => useAppSettings());
    expect(result.current.showSessionIdHover).toBe(false);
  });

  it("reads initial value from localStorage", () => {
    localStorage.setItem("scriptordb:show_session_id_hover", "true");
    const { result } = renderHook(() => useAppSettings());
    expect(result.current.showSessionIdHover).toBe(true);
  });

  it("setShowSessionIdHover updates state and localStorage", () => {
    const { result } = renderHook(() => useAppSettings());

    act(() => {
      result.current.setShowSessionIdHover(true);
    });

    expect(result.current.showSessionIdHover).toBe(true);
    expect(localStorage.getItem("scriptordb:show_session_id_hover")).toBe(
      "true",
    );

    act(() => {
      result.current.setShowSessionIdHover(false);
    });

    expect(result.current.showSessionIdHover).toBe(false);
    expect(localStorage.getItem("scriptordb:show_session_id_hover")).toBe(
      "false",
    );
  });

  it("handles localStorage errors gracefully", () => {
    const original = localStorage.setItem;
    localStorage.setItem = () => {
      throw new Error("quota exceeded");
    };
    try {
      const { result } = renderHook(() => useAppSettings());
      expect(() => {
        act(() => {
          result.current.setShowSessionIdHover(true);
        });
      }).not.toThrow();
    } finally {
      localStorage.setItem = original;
    }
  });
});
