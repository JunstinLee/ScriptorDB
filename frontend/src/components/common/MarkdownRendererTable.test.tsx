import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import MarkdownRenderer from "../../components/common/MarkdownRenderer";
import { ThemeProvider } from "../../hooks/useTheme";
import { renderWithTheme } from "../../test/markdownHarness";

function bigTable(rows: number): string {
  const body = Array.from({ length: rows }, (_, i) => `| ${i} | value ${i} |`).join("\n");
  return `| id | val |\n|---|---|\n${body}`;
}

describe("MarkdownRenderer tables", () => {
  it("renders tables", () => {
    const content = "| a | b |\n|---|---|\n| 1 | 2 |";
    renderWithTheme(<MarkdownRenderer content={content} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("a")).toBeInTheDocument();
    expect(screen.getByText("b")).toBeInTheDocument();
  });

  it("paginates tables with more than one page of rows", async () => {
    const user = userEvent.setup();
    renderWithTheme(<MarkdownRenderer content={bigTable(25)} />);

    expect(screen.getByText("25 rows x 2 cols")).toBeInTheDocument();
    expect(screen.getByText("1 / 2")).toBeInTheDocument();

    expect(screen.getByText("value 0")).toBeInTheDocument();
    expect(screen.getByText("value 19")).toBeInTheDocument();
    expect(screen.queryByText("value 20")).not.toBeInTheDocument();

    await user.click(screen.getByText("Next"));
    expect(screen.getByText("2 / 2")).toBeInTheDocument();
    expect(screen.getByText("value 20")).toBeInTheDocument();
    expect(screen.queryByText("value 0")).not.toBeInTheDocument();

    await user.click(screen.getByText("Prev"));
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
    expect(screen.getByText("value 0")).toBeInTheDocument();
  });

  it("keeps the current page when the renderer updates", async () => {
    const user = userEvent.setup();
    const content = bigTable(25);
    const { rerender } = renderWithTheme(<MarkdownRenderer content={content} />);

    await user.click(screen.getByText("Next"));
    expect(screen.getByText("2 / 2")).toBeInTheDocument();

    rerender(
      <ThemeProvider>
        <MarkdownRenderer content={`${content}\n`} />
      </ThemeProvider>,
    );

    expect(screen.getByText("2 / 2")).toBeInTheDocument();
    expect(screen.getByText("value 20")).toBeInTheDocument();
  });

  it("does not paginate small tables", () => {
    renderWithTheme(<MarkdownRenderer content={bigTable(3)} />);

    expect(screen.queryByText(/rows x/)).not.toBeInTheDocument();
    expect(screen.queryByText("Next")).not.toBeInTheDocument();
    expect(screen.getByText("value 2")).toBeInTheDocument();
  });
});
