import { useCallback, useState, type CSSProperties } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { PrismLight as SyntaxHighlighter } from "react-syntax-highlighter";
import { useTheme } from "../../hooks/useTheme";

import javascript from "react-syntax-highlighter/dist/esm/languages/prism/javascript";
import typescript from "react-syntax-highlighter/dist/esm/languages/prism/typescript";
import tsx from "react-syntax-highlighter/dist/esm/languages/prism/tsx";
import python from "react-syntax-highlighter/dist/esm/languages/prism/python";
import sql from "react-syntax-highlighter/dist/esm/languages/prism/sql";
import bash from "react-syntax-highlighter/dist/esm/languages/prism/bash";
import json from "react-syntax-highlighter/dist/esm/languages/prism/json";
import yaml from "react-syntax-highlighter/dist/esm/languages/prism/yaml";
import markdown from "react-syntax-highlighter/dist/esm/languages/prism/markdown";
import html from "react-syntax-highlighter/dist/esm/languages/prism/markup";

SyntaxHighlighter.registerLanguage("javascript", javascript);
SyntaxHighlighter.registerLanguage("typescript", typescript);
SyntaxHighlighter.registerLanguage("tsx", tsx);
SyntaxHighlighter.registerLanguage("python", python);
SyntaxHighlighter.registerLanguage("sql", sql);
SyntaxHighlighter.registerLanguage("bash", bash);
SyntaxHighlighter.registerLanguage("json", json);
SyntaxHighlighter.registerLanguage("yaml", yaml);
SyntaxHighlighter.registerLanguage("markdown", markdown);
SyntaxHighlighter.registerLanguage("html", html);

interface MarkdownRendererProps {
  content: string;
}

const prismLight: Record<string, CSSProperties> = {
  'code[class*="language-"]': { color: "#1A1B1F", background: "none", fontFamily: "'JetBrains Mono', monospace", fontSize: "0.8125rem", lineHeight: "1.5", tabSize: 2, hyphens: "none" },
  'pre[class*="language-"]': { color: "#1A1B1F", background: "none", fontFamily: "'JetBrains Mono', monospace", fontSize: "0.8125rem", lineHeight: "1.5", tabSize: 2, hyphens: "none", padding: 0, margin: 0 },
  comment: { color: "#6B6F78", fontStyle: "italic" },
  prolog: { color: "#6B6F78" },
  doctype: { color: "#6B6F78" },
  cdata: { color: "#6B6F78" },
  punctuation: { color: "#6B6F78" },
  property: { color: "#2E5BFF" },
  tag: { color: "#2E5BFF" },
  boolean: { color: "#D98A16" },
  number: { color: "#D98A16" },
  constant: { color: "#D98A16" },
  symbol: { color: "#D98A16" },
  selector: { color: "#3A8A5E" },
  "attr-name": { color: "#3A8A5E" },
  string: { color: "#3A8A5E" },
  char: { color: "#3A8A5E" },
  builtin: { color: "#2E5BFF" },
  inserted: { color: "#3A8A5E" },
  operator: { color: "#6B6F78" },
  entity: { color: "#2E5BFF" },
  url: { color: "#2E5BFF" },
  atrule: { color: "#2E5BFF" },
  "attr-value": { color: "#3A8A5E" },
  keyword: { color: "#C94036" },
  "function": { color: "#2E5BFF" },
  "class-name": { color: "#C94036" },
  regex: { color: "#D98A16" },
  important: { color: "#D98A16", fontWeight: "bold" },
  variable: { color: "#D98A16" },
  deleted: { color: "#C94036" },
  namespace: { opacity: 0.7 },
};

const prismDark: Record<string, CSSProperties> = {
  'code[class*="language-"]': { color: "#E8E6E1", background: "none", fontFamily: "'JetBrains Mono', monospace", fontSize: "0.8125rem", lineHeight: "1.5", tabSize: 2, hyphens: "none" },
  'pre[class*="language-"]': { color: "#E8E6E1", background: "none", fontFamily: "'JetBrains Mono', monospace", fontSize: "0.8125rem", lineHeight: "1.5", tabSize: 2, hyphens: "none", padding: 0, margin: 0 },
  comment: { color: "#8C9099", fontStyle: "italic" },
  prolog: { color: "#8C9099" },
  doctype: { color: "#8C9099" },
  cdata: { color: "#8C9099" },
  punctuation: { color: "#8C9099" },
  property: { color: "#5B8AFF" },
  tag: { color: "#5B8AFF" },
  boolean: { color: "#F0A820" },
  number: { color: "#F0A820" },
  constant: { color: "#F0A820" },
  symbol: { color: "#F0A820" },
  selector: { color: "#5FB382" },
  "attr-name": { color: "#5FB382" },
  string: { color: "#5FB382" },
  char: { color: "#5FB382" },
  builtin: { color: "#5B8AFF" },
  inserted: { color: "#5FB382" },
  operator: { color: "#8C9099" },
  entity: { color: "#5B8AFF" },
  url: { color: "#5B8AFF" },
  atrule: { color: "#5B8AFF" },
  "attr-value": { color: "#5FB382" },
  keyword: { color: "#EF5350" },
  "function": { color: "#5B8AFF" },
  "class-name": { color: "#EF5350" },
  regex: { color: "#F0A820" },
  important: { color: "#F0A820", fontWeight: "bold" },
  variable: { color: "#F0A820" },
  deleted: { color: "#EF5350" },
  namespace: { opacity: 0.7 },
};

function CodeBlock({ className, children }: { className?: string; children?: React.ReactNode }) {
  const { isDark } = useTheme();
  const match = /language-(\w+)/.exec(className || "");
  const language = match?.[1];

  const isInline = !match && !className && typeof children === "string" && !children.includes("\n");

  if (isInline) {
    return (
      <code className="bg-surface border border-grid font-mono text-[13px] rounded px-1.5 py-0.5 break-all">
        {children}
      </code>
    );
  }

  const code = String(children).replace(/\n$/, "");

  return (
    <CodeBlockWrapper language={language} code={code}>
      <SyntaxHighlighter
        style={(isDark ? prismDark : prismLight) as Record<string, CSSProperties>}
        language={language ?? "text"}
        PreTag="div"
        customStyle={{
          margin: 0,
          borderRadius: 0,
          background: "transparent",
          fontSize: "0.8125rem",
          lineHeight: "1.5",
        }}
        codeTagProps={{ style: { fontFamily: "inherit" } }}
      >
        {code}
      </SyntaxHighlighter>
    </CodeBlockWrapper>
  );
}

function CodeBlockWrapper({
  language,
  code,
  children,
}: {
  language: string | undefined;
  code: string;
  children: React.ReactNode;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard unavailable
    }
  }, [code]);

  return (
    <div className="rounded-lg overflow-hidden border border-grid my-2">
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface/60 border-b border-grid">
        <span className="text-[11px] text-graphite font-mono font-medium uppercase tracking-[0.08em]">
          {language ?? "text"}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="text-[11px] text-graphite hover:text-cobalt transition-colors"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="max-h-96 overflow-auto bg-paper dark:bg-[#1a1d24] p-3">
        {children}
      </div>
    </div>
  );
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  if (!content) return null;

  return (
    <div className="text-[14px] leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children, ...props }) => (
            <h1 className="font-semibold text-lg mt-4 mb-2 first:mt-0" {...props}>{children}</h1>
          ),
          h2: ({ children, ...props }) => (
            <h2 className="font-semibold text-base mt-3 mb-1.5 first:mt-0" {...props}>{children}</h2>
          ),
          h3: ({ children, ...props }) => (
            <h3 className="font-semibold text-sm mt-3 mb-1 first:mt-0" {...props}>{children}</h3>
          ),
          h4: ({ children, ...props }) => (
            <h4 className="font-semibold text-sm mt-2 mb-1 first:mt-0" {...props}>{children}</h4>
          ),
          h5: ({ children, ...props }) => (
            <h5 className="font-semibold text-xs mt-2 mb-1 first:mt-0" {...props}>{children}</h5>
          ),
          h6: ({ children, ...props }) => (
            <h6 className="font-semibold text-xs mt-2 mb-1 first:mt-0" {...props}>{children}</h6>
          ),
          p: ({ children, ...props }) => (
            <p className="mb-3 last:mb-0" {...props}>{children}</p>
          ),
          ul: ({ children, ...props }) => (
            <ul className="list-disc pl-5 mb-3 last:mb-0 space-y-0.5" {...props}>{children}</ul>
          ),
          ol: ({ children, ...props }) => (
            <ol className="list-decimal pl-5 mb-3 last:mb-0 space-y-0.5" {...props}>{children}</ol>
          ),
          li: ({ children, ...props }) => (
            <li className="mb-0.5 last:mb-0" {...props}>{children}</li>
          ),
          a: ({ children, ...props }) => (
            <a className="text-cobalt underline break-all" target="_blank" rel="noopener noreferrer" {...props}>{children}</a>
          ),
          blockquote: ({ children, ...props }) => (
            <blockquote className="border-l-2 border-grid pl-3 italic text-graphite mb-3 last:mb-0" {...props}>{children}</blockquote>
          ),
          hr: (props) => (
            <hr className="my-3 border-grid" {...props} />
          ),
          table: ({ children, ...props }) => (
            <div className="overflow-x-auto mb-3 last:mb-0">
              <table className="w-full border-collapse text-left text-xs" {...props}>{children}</table>
            </div>
          ),
          thead: ({ children, ...props }) => (
            <thead className="border-b border-grid" {...props}>{children}</thead>
          ),
          tbody: ({ children, ...props }) => (
            <tbody {...props}>{children}</tbody>
          ),
          tr: ({ children, ...props }) => (
            <tr className="border-b border-grid last:border-0" {...props}>{children}</tr>
          ),
          th: ({ children, ...props }) => (
            <th className="px-3 py-1.5 font-semibold" {...props}>{children}</th>
          ),
          td: ({ children, ...props }) => (
            <td className="px-3 py-1.5" {...props}>{children}</td>
          ),
          code: (props) => <CodeBlock {...props} />,
          pre: ({ children, ...props }) => (
            <pre className="m-0" {...props}>{children}</pre>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
