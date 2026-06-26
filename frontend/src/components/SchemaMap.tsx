import { useCallback, useMemo } from "react";
import type { SchemaTable } from "../types";
import {
  computeLayout,
  extractForeignKeys,
  type FKEdge,
  type SchemaMapLayout,
} from "../utils/schemaMap";

interface SchemaMapProps {
  tables: SchemaTable[];
  onTableClick?: (tableName: string) => void;
}

const TABLE_RADIUS = 6;
const HEADER_HEIGHT = 32;
const COL_ROW_HEIGHT = 16;
const FONT_MONO = "JetBrains Mono, ui-monospace, monospace";

export default function SchemaMap({ tables, onTableClick }: SchemaMapProps) {
  const handleClick = useCallback(
    (tableName: string) => {
      onTableClick?.(tableName);
    },
    [onTableClick],
  );

  const edges = useMemo(() => extractForeignKeys(tables), [tables]);
  const layout = useMemo(() => computeLayout(tables), [tables]);
  const layoutMap = useMemo(() => {
    const map = new Map<string, SchemaMapLayout>();
    for (const item of layout) {
      map.set(item.tableName.toLowerCase(), item);
    }
    return map;
  }, [layout]);

  if (tables.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-muted">
        <p className="text-xs">No tables found in this workspace.</p>
      </div>
    );
  }

  const svgWidth = Math.max(
    320,
    ...layout.map((l) => l.x + l.width),
  ) + 20;

  const svgHeight =
    Math.max(
      200,
      ...layout.map((l) => l.y + l.height),
    ) + 20;

  function tableY(tableName: string): number | null {
    const lo = layoutMap.get(tableName.toLowerCase());
    return lo ? lo.y + lo.height / 2 : null;
  }

  function drawEdge(edge: FKEdge): React.ReactNode {
    const from = layoutMap.get(edge.fromTable);
    const to = layoutMap.get(edge.toTable);
    if (!from || !to) return null;

    const x1 = from.x + (from.width * 3) / 4;
    const y1 = tableY(edge.fromTable) ?? from.y + from.height / 2;
    const x2 = to.x + to.width / 4;
    const y2 = tableY(edge.toTable) ?? to.y + to.height / 2;

    const midX = (x1 + x2) / 2;

    const d = `M${x1},${y1} C${midX},${y1} ${midX},${y2} ${x2},${y2}`;

    return (
      <path
        key={`${edge.fromTable}-${edge.fromCol}-${edge.toTable}-${edge.toCol}`}
        d={d}
        fill="none"
        stroke="var(--grid)"
        strokeWidth={1}
        markerEnd="url(#cobaltArrow)"
      />
    );
  }

  return (
    <div className="overflow-auto max-h-[320px] border-b border-grid pb-2">
      <svg
        width={svgWidth}
        height={svgHeight}
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        className="block"
        style={{ minWidth: svgWidth }}
      >
        <defs>
          <marker
            id="cobaltArrow"
            viewBox="0 0 10 10"
            refX={8}
            refY={5}
            markerWidth={6}
            markerHeight={6}
            orient="auto-start-reverse"
          >
            <circle cx={5} cy={5} r={3} fill="var(--cobalt)" />
          </marker>
        </defs>

        {edges.map(drawEdge)}

        {layout.map((lo) => {
          const table = tables.find(
            (t) => t.name.toLowerCase() === lo.tableName.toLowerCase(),
          );
          if (!table) return null;

          const displayColumns = table.columns.slice(0, 8);
          const hasMore = table.columns.length > 8;

          return (
            <g
              key={lo.tableName}
              onClick={() => handleClick(lo.tableName)}
              className="cursor-pointer"
            >
              <rect
                x={lo.x}
                y={lo.y}
                width={lo.width}
                height={lo.height}
                rx={TABLE_RADIUS}
                fill="var(--surface)"
                stroke="var(--grid)"
                strokeWidth={1}
              />

              <line
                x1={lo.x}
                y1={lo.y + HEADER_HEIGHT}
                x2={lo.x + lo.width}
                y2={lo.y + HEADER_HEIGHT}
                stroke="var(--grid)"
                strokeWidth={1}
              />

              <text
                x={lo.x + 10}
                y={lo.y + 20}
                fontFamily={FONT_MONO}
                fontSize={13}
                fontWeight={600}
                fill="var(--ink)"
              >
                {table.name}
              </text>

              {displayColumns.map((col, i) => {
                const colY =
                  lo.y + HEADER_HEIGHT + 10 + i * COL_ROW_HEIGHT + 10;
                return (
                  <g key={col.name}>
                    {col.pk && (
                      <circle
                        cx={lo.x + 8}
                        cy={colY - 4}
                        r={3}
                        fill="var(--cobalt)"
                      />
                    )}
                    {!col.pk &&
                      edges.some(
                        (e) =>
                          e.fromTable === lo.tableName.toLowerCase() &&
                          e.fromCol === col.name.toLowerCase(),
                      ) && (
                        <circle
                          cx={lo.x + 8}
                          cy={colY - 4}
                          r={3}
                          fill="var(--amber)"
                        />
                      )}
                    <text
                      x={lo.x + 16}
                      y={colY}
                      fontFamily={FONT_MONO}
                      fontSize={11}
                      fill="var(--graphite)"
                    >
                      {col.name}
                    </text>
                    <text
                      x={lo.x + lo.width - 8}
                      y={colY}
                      fontFamily={FONT_MONO}
                      fontSize={10}
                      fill="var(--graphite)"
                      textAnchor="end"
                      opacity={0.6}
                    >
                      {col.type}
                    </text>
                  </g>
                );
              })}

              {hasMore && (
                <text
                  x={lo.x + 16}
                  y={
                    lo.y +
                    HEADER_HEIGHT +
                    10 +
                    displayColumns.length * COL_ROW_HEIGHT +
                    10
                  }
                  fontFamily={FONT_MONO}
                  fontSize={10}
                  fill="var(--graphite)"
                  opacity={0.5}
                >
                  +{table.columns.length - 8} more…
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
