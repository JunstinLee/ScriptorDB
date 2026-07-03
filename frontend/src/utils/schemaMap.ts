import type { SchemaTable } from "../types";

export interface FKEdge {
  fromTable: string;
  fromCol: string;
  toTable: string;
  toCol: string;
}

export function extractForeignKeys(tables: SchemaTable[]): FKEdge[] {
  const edges: FKEdge[] = [];
  const tableNames = new Set(tables.map((t) => t.name.toLowerCase()));

  for (const table of tables) {
    const sql = table.sql.toUpperCase();
    const fkRegex = /FOREIGN\s+KEY\s*\(\s*(\w+)\s*\)\s*REFERENCES\s+(\w+)\s*\(\s*(\w+)\s*\)/gi;
    let match: RegExpExecArray | null;
    while ((match = fkRegex.exec(sql)) !== null) {
      const fromCol = match[1].toLowerCase();
      const toTable = match[2].toLowerCase();
      const toCol = match[3].toLowerCase();
      const fromTable = table.name.toLowerCase();
      if (tableNames.has(toTable)) {
        edges.push({
          fromTable,
          fromCol,
          toTable,
          toCol,
        });
      }
    }
  }

  if (edges.length > 0) return edges;

  for (const table of tables) {
    for (const col of table.columns) {
      if (col.name.toLowerCase().endsWith("_id")) {
        const candidate = col.name.toLowerCase().replace(/_id$/, "");
        const candidates = [
          candidate,
          candidate + "s",
        ];
        for (const c of candidates) {
          if (tableNames.has(c) && c !== table.name.toLowerCase()) {
            edges.push({
              fromTable: table.name.toLowerCase(),
              fromCol: col.name.toLowerCase(),
              toTable: c,
              toCol: "id",
            });
          }
        }
      }
    }
  }

  return edges;
}

export interface SchemaMapLayout {
  tableName: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

const TABLE_WIDTH = 220;
const COL_ROW_HEIGHT = 16;
const TABLE_HEADER_HEIGHT = 32;
const TABLE_PADDING = 10;
const VERTICAL_GAP = 60;
const HORIZONTAL_GAP = 40;

export function computeLayout(tables: SchemaTable[]): SchemaMapLayout[] {
  const layout: SchemaMapLayout[] = [];
  let currentX = 0;
  let currentY = 0;
  let maxRowHeight = 0;

  for (const table of tables) {
    const colCount = Math.min(table.columns.length, 8);
    const height = TABLE_HEADER_HEIGHT + colCount * COL_ROW_HEIGHT + TABLE_PADDING;

    if (currentX > 0 && currentX + TABLE_WIDTH > 220) {
      currentX = 0;
      currentY += maxRowHeight + VERTICAL_GAP;
      maxRowHeight = 0;
    }

    layout.push({
      tableName: table.name,
      x: currentX,
      y: currentY,
      width: TABLE_WIDTH,
      height,
    });

    currentX += TABLE_WIDTH + HORIZONTAL_GAP;
    maxRowHeight = Math.max(maxRowHeight, height);
  }

  return layout;
}
