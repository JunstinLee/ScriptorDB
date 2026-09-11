import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import MarkdownRenderer from "../../components/common/MarkdownRenderer";
import { mockClipboard, renderWithTheme } from "../../test/markdownHarness";

describe("MarkdownRenderer copy button", () => {
  it("copies code block content on button click", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    mockClipboard(writeText);

    renderWithTheme(<MarkdownRenderer content={"```js\nconst x = 1;\n```"} />);

    await user.click(screen.getByText("Copy"));

    expect(writeText).toHaveBeenCalledWith("const x = 1;");
  });

  it("handles clipboard errors gracefully", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    mockClipboard(writeText);

    renderWithTheme(<MarkdownRenderer content={"```js\ncode\n```"} />);

    await expect(user.click(screen.getByText("Copy"))).resolves.not.toThrow();
  });

  it("shows Copied feedback after copying", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    mockClipboard(writeText);

    renderWithTheme(<MarkdownRenderer content={"```js\ncode\n```"} />);

    await user.click(screen.getByText("Copy"));

    expect(await screen.findByText("Copied")).toBeInTheDocument();
  });
});
