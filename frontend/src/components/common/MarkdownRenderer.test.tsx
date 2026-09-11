import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import MarkdownRenderer from "../../components/common/MarkdownRenderer";
import { renderWithTheme } from "../../test/markdownHarness";

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
    const pythonElements = screen.getAllByText((_content, element) => element?.tagName === "SPAN" && element?.textContent === "python");
    expect(pythonElements.length).toBeGreaterThanOrEqual(1);
    const codeElements = screen.getAllByText((_content, element) => element?.tagName === "CODE" && element?.textContent?.includes("print"));
    expect(codeElements.length).toBeGreaterThanOrEqual(1);
  });

  it("renders code blocks as text when no language", () => {
    const content = "```\nplain text\n```";
    renderWithTheme(<MarkdownRenderer content={content} />);
    expect(screen.getByText("text")).toBeInTheDocument();
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
});
