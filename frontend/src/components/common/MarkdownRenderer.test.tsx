import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MarkdownRenderer from "../../components/common/MarkdownRenderer";
import { ThemeProvider } from "../../hooks/useTheme";

function mockClipboard(writeText: ReturnType<typeof vi.fn>) {
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    writable: true,
    configurable: true,
  });
}

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe("MarkdownRenderer", () => {
  it("returns null for empty content", () => {
    const { container } = renderWithTheme(<MarkdownRenderer content="" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders headings", () => {
    const content = "# H1\n## H2\n### H3";
    renderWithTheme(<MarkdownRenderer content={content} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("H1");
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("H2");
    expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent("H3");
  });

  it("renders unordered lists", () => {
    const content = "- item 1\n- item 2\n- item 3";
    renderWithTheme(<MarkdownRenderer content={content} />);
    expect(screen.getByText("item 1")).toBeInTheDocument();
    expect(screen.getByText("item 2")).toBeInTheDocument();
    expect(screen.getByText("item 3")).toBeInTheDocument();
  });

  it("renders ordered lists", () => {
    const content = "1. first\n2. second\n3. third";
    renderWithTheme(<MarkdownRenderer content={content} />);
    expect(screen.getByText("first")).toBeInTheDocument();
    expect(screen.getByText("second")).toBeInTheDocument();
  });

  it("renders inline code", () => {
    const content = "Use `npm install` to get started";
    renderWithTheme(<MarkdownRenderer content={content} />);
    const code = screen.getByText("npm install");
    expect(code.tagName).toBe("CODE");
  });

  it("renders code blocks with language label", () => {
    const content = "```python\nprint('hello')\n```";
    renderWithTheme(<MarkdownRenderer content={content} />);
    expect(screen.getByText("python")).toBeInTheDocument();
    expect(screen.getByText((_content, element) => element?.textContent === "print('hello')")).toBeInTheDocument();
  });

  it("renders code blocks as text when no language", () => {
    const content = "```\nplain text\n```";
    renderWithTheme(<MarkdownRenderer content={content} />);
    expect(screen.getByText("text")).toBeInTheDocument();
  });

  it("renders tables", () => {
    const content = "| a | b |\n|---|---|\n| 1 | 2 |";
    renderWithTheme(<MarkdownRenderer content={content} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("a")).toBeInTheDocument();
    expect(screen.getByText("b")).toBeInTheDocument();
  });

  it("renders blockquotes", () => {
    const content = "> quoted text";
    renderWithTheme(<MarkdownRenderer content={content} />);
    expect(screen.getByText("quoted text")).toBeInTheDocument();
  });

  it("renders links with target blank", () => {
    const content = "[example](https://example.com)";
    renderWithTheme(<MarkdownRenderer content={content} />);
    const link = screen.getByRole("link", { name: "example" });
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("renders horizontal rules", () => {
    const content = "---";
    renderWithTheme(<MarkdownRenderer content={content} />);
    expect(screen.getByRole("separator")).toBeInTheDocument();
  });

  it("does not render raw HTML", () => {
    const content = "<script>alert('xss')</script>";
    renderWithTheme(<MarkdownRenderer content={content} />);
    expect(screen.queryByText("alert('xss')")).not.toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
  });

  it("handles bold and italic", () => {
    const content = "**bold** and *italic*";
    renderWithTheme(<MarkdownRenderer content={content} />);
    expect(screen.getByText("bold")).toBeInTheDocument();
    expect(screen.getByText("italic")).toBeInTheDocument();
  });

  it("copies code block content on button click", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    mockClipboard(writeText);

    const content = "```js\nconst x = 1;\n```";
    renderWithTheme(<MarkdownRenderer content={content} />);

    const copyButton = screen.getByText("Copy");
    await user.click(copyButton);

    expect(writeText).toHaveBeenCalledWith("const x = 1;");
  });

  it("handles clipboard errors gracefully", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    mockClipboard(writeText);

    const content = "```js\ncode\n```";
    renderWithTheme(<MarkdownRenderer content={content} />);

    const copyButton = screen.getByText("Copy");
    await expect(user.click(copyButton)).resolves.not.toThrow();
  });

  it("shows Copied feedback after copying", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    mockClipboard(writeText);

    vi.useFakeTimers();

    const content = "```js\ncode\n```";
    renderWithTheme(<MarkdownRenderer content={content} />);

    const copyButton = screen.getByText("Copy");
    await user.click(copyButton);

    expect(screen.getByText("Copied!")).toBeInTheDocument();

    vi.advanceTimersByTime(2000);

    expect(screen.getByText("Copy")).toBeInTheDocument();

    vi.useRealTimers();
  });
});
