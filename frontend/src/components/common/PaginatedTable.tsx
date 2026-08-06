import { useEffect, useState, type ReactNode } from "react";
import { Button, Chip } from "@heroui/react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Element } from "hast";
import { t } from "../../i18n";
import { PaginationContext, TABLE_PAGE_SIZE } from "./tablePagination";

interface HastNode {
  type?: string;
  tagName?: string;
  children?: HastNode[];
}

function isElement(node: HastNode | undefined): node is Element {
  return (
    !!node &&
    typeof node === "object" &&
    node.type === "element" &&
    typeof node.tagName === "string"
  );
}

function countBodyRows(node: Element | undefined): number {
  if (!node) return 0;
  let count = 0;
  for (const child of node.children ?? []) {
    if (isElement(child) && child.tagName === "tbody") {
      for (const row of child.children ?? []) {
        if (isElement(row) && row.tagName === "tr") count++;
      }
    }
  }
  return count;
}

function countColumns(node: Element | undefined): number {
  if (!node) return 0;
  for (const child of node.children ?? []) {
    if (isElement(child)) {
      for (const row of child.children ?? []) {
        if (isElement(row) && row.tagName === "tr") {
          let cells = 0;
          for (const cell of row.children ?? []) {
            if (isElement(cell) && (cell.tagName === "th" || cell.tagName === "td")) {
              cells++;
            }
          }
          if (cells > 0) return cells;
        }
      }
    }
  }
  return 0;
}

interface PaginatedTableProps {
  node?: Element;
  children: ReactNode;
}

export default function PaginatedTable({ node, children }: PaginatedTableProps) {
  const total = countBodyRows(node);
  const cols = countColumns(node);
  const totalPages = Math.max(1, Math.ceil(total / TABLE_PAGE_SIZE));
  const paginated = total > TABLE_PAGE_SIZE;
  const [page, setPage] = useState(0);

  useEffect(() => {
    setPage((p) => Math.min(p, totalPages - 1));
  }, [totalPages]);

  return (
    <PaginationContext.Provider
      value={{ page, pageSize: TABLE_PAGE_SIZE, total, paginated }}
    >
      <div
        className={
          paginated
            ? "rounded-lg border border-grid overflow-hidden mb-3 last:mb-0"
            : "overflow-x-auto mb-3 last:mb-0"
        }
      >
        {paginated && (
          <div className="flex items-center justify-between gap-2 px-3 py-1.5 border-b border-grid bg-surface/60">
            <Chip size="sm" variant="soft">
              {t("table.rows", { rows: total, cols })}
            </Chip>
            <div className="flex items-center gap-1.5">
              <Button
                size="sm"
                variant="ghost"
                isDisabled={page === 0}
                onPress={() => setPage((p) => Math.max(0, p - 1))}
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                {t("table.prev")}
              </Button>
              <span className="text-[11px] text-muted whitespace-nowrap">
                {t("table.page", { page: page + 1, total: totalPages })}
              </span>
              <Button
                size="sm"
                variant="ghost"
                isDisabled={page >= totalPages - 1}
                onPress={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              >
                {t("table.next")}
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}
        {paginated ? (
          <div className="overflow-auto max-h-96 bg-paper dark:bg-[#1a1d24]">
            <table className="w-full border-collapse text-left text-xs">
              {children}
            </table>
          </div>
        ) : (
          <table className="w-full border-collapse text-left text-xs">
            {children}
          </table>
        )}
      </div>
    </PaginationContext.Provider>
  );
}
