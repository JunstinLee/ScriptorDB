import { useCallback, useState, type CSSProperties } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { PrismLight as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
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

function CodeBlock({ className, children }: { className?: string; children?: React.ReactNode }) {
  const { isDark } = useTheme();
  const match = /language-(\w+)/.exec(className || "");
  const language = match?.[1];

  const isInline = !match && !className && typeof children === "string" && !children.includes("\n");

  if (isInline) {
    return (
      <code className="bg-default-100 text-default-foreground rounded px-1.5 py-0.5 font-mono text-xs break-all">
        {children}
      </code>
    );
  }

  const code = String(children).replace(/\n$/, "");

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
    } catch {
      // clipboard unavailable
    }
  }, [code]);

  return (
    <CodeBlockWrapper language={language} onCopy={handleCopy}>
      <SyntaxHighlighter
        style={(isDark ? oneDark : oneLight) as Record<string, CSSProperties>}
        language={language ?? "text"}
        PreTag="div"
        customStyle={{
          margin: 0,
          borderRadius: 0,
          background: "transparent",
          fontSize: "0.75rem",
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
  onCopy,
  children,
}: {
  language: string | undefined;
  onCopy: () => void;
  children: React.ReactNode;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await onCopy();
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group/code rounded-lg overflow-hidden border border-default-200 my-2">
      <div className="flex items-center justify-between px-3 py-1.5 bg-default-100/80 border-b border-default-200">
        <span className="text-xs text-muted font-mono">
          {language ?? "text"}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="text-xs text-muted hover:text-foreground transition-colors"
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      <div className="max-h-96 overflow-auto bg-default-50 dark:bg-default-900">
        {children}
      </div>
    </div>
  );
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  if (!content) return null;

  return (
    <div className="text-sm leading-relaxed">
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
            <a className="text-accent underline break-all" target="_blank" rel="noopener noreferrer" {...props}>{children}</a>
          ),
          blockquote: ({ children, ...props }) => (
            <blockquote className="border-l-2 border-default-300 pl-3 italic text-muted mb-3 last:mb-0" {...props}>{children}</blockquote>
          ),
          hr: (props) => (
            <hr className="my-3 border-default-200" {...props} />
          ),
          table: ({ children, ...props }) => (
            <div className="overflow-x-auto mb-3 last:mb-0">
              <table className="w-full border-collapse text-left text-xs" {...props}>{children}</table>
            </div>
          ),
          thead: ({ children, ...props }) => (
            <thead className="border-b border-default-300" {...props}>{children}</thead>
          ),
          tbody: ({ children, ...props }) => (
            <tbody {...props}>{children}</tbody>
          ),
          tr: ({ children, ...props }) => (
            <tr className="border-b border-default-200 last:border-0" {...props}>{children}</tr>
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
