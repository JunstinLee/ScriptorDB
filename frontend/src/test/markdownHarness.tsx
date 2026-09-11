import { render } from "@testing-library/react";
import type { Mock } from "vitest";

import { ThemeProvider } from "../hooks/useTheme";

/** 用主题 Provider 包一层渲染（MarkdownRenderer 等依赖 useTheme 的组件用）。 */
export function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

/** 替换 navigator.clipboard.writeText，供复制类用例断言。 */
export function mockClipboard(writeText: Mock) {
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    writable: true,
    configurable: true,
  });
}
