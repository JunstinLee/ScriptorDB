import { describe, expect, it } from "vitest";
import { extractForeignKeys, computeLayout } from "./schemaMap";
import type { SchemaTable } from "../types";

function table(name: string, sql: string, cols: string[] = ["id"]): SchemaTable {
  return {
    name,
    sql,
    columns: cols.map((c) => ({
      name: c,
      type: "TEXT",
      pk: false,
      notnull: false,
      default_value: null,
      autoincrement: false,
    })),
  };
}

describe("extractForeignKeys", () => {
  it("returns empty for no tables", () => {
    expect(extractForeignKeys([])).toEqual([]);
  });

  it("parses explicit FOREIGN KEY clauses", () => {
    const tables = [
      table("users", "CREATE TABLE users (id INTEGER PRIMARY KEY)"),
      table(
        "orders",
        "CREATE TABLE orders (id INTEGER, user_id INTEGER, FOREIGN KEY (user_id) REFERENCES users(id))",
        ["id", "user_id"],
      ),
    ];

    expect(extractForeignKeys(tables)).toEqual([
      {
        fromTable: "orders",
        fromCol: "user_id",
        toTable: "users",
        toCol: "id",
      },
    ]);
  });

  it("parses multiple FK clauses per table", () => {
    const tables = [
      table("users", "CREATE TABLE users (id INTEGER)"),
      table("products", "CREATE TABLE products (id INTEGER)"),
      table(
        "order_items",
        "CREATE TABLE order_items (id INTEGER, order_id INTEGER, product_id INTEGER, FOREIGN KEY (order_id) REFERENCES orders(id), FOREIGN KEY (product_id) REFERENCES products(id))",
        ["id", "order_id", "product_id"],
      ),
      table("orders", "CREATE TABLE orders (id INTEGER)"),
    ];

    expect(extractForeignKeys(tables)).toEqual([
      {
        fromTable: "order_items",
        fromCol: "order_id",
        toTable: "orders",
        toCol: "id",
      },
      {
        fromTable: "order_items",
        fromCol: "product_id",
        toTable: "products",
        toCol: "id",
      },
    ]);
  });

  it("is case-insensitive for SQL, table names and columns", () => {
    const tables = [
      table("Users", "CREATE TABLE Users (ID INTEGER)"),
      table(
        "Orders",
        "CREATE TABLE Orders (ID INTEGER, USER_ID INTEGER, FOREIGN KEY (user_id) REFERENCES Users(ID))",
        ["ID", "USER_ID"],
      ),
    ];

    expect(extractForeignKeys(tables)).toEqual([
      {
        fromTable: "orders",
        fromCol: "user_id",
        toTable: "users",
        toCol: "id",
      },
    ]);
  });

  it("ignores FK references to tables that do not exist", () => {
    const tables = [
      table(
        "orders",
        "CREATE TABLE orders (id INTEGER, ghost_id INTEGER, FOREIGN KEY (ghost_id) REFERENCES ghosts(id))",
        ["id", "ghost_id"],
      ),
    ];

    expect(extractForeignKeys(tables)).toEqual([]);
  });

  it("falls back to _id naming heuristic when no explicit FK exists", () => {
    const tables = [
      table("users", "CREATE TABLE users (id INTEGER)"),
      table("orders", "CREATE TABLE orders (id INTEGER, user_id INTEGER)", [
        "id",
        "user_id",
      ]),
    ];

    expect(extractForeignKeys(tables)).toEqual([
      {
        fromTable: "orders",
        fromCol: "user_id",
        toTable: "users",
        toCol: "id",
      },
    ]);
  });

  it("heuristic tries pluralized table name", () => {
    const tables = [
      table("authors", "CREATE TABLE authors (id INTEGER)"),
      table("books", "CREATE TABLE books (id INTEGER, author_id INTEGER)", [
        "id",
        "author_id",
      ]),
    ];

    expect(extractForeignKeys(tables)).toEqual([
      {
        fromTable: "books",
        fromCol: "author_id",
        toTable: "authors",
        toCol: "id",
      },
    ]);
  });

  it("heuristic excludes self-references", () => {
    const tables = [
      table("user", "CREATE TABLE user (id INTEGER, user_id INTEGER)", [
        "id",
        "user_id",
      ]),
    ];

    expect(extractForeignKeys(tables)).toEqual([]);
  });

  it("does not run heuristic when explicit FK was found", () => {
    const tables = [
      table("users", "CREATE TABLE users (id INTEGER)"),
      table(
        "orders",
        "CREATE TABLE orders (id INTEGER, user_id INTEGER, team_id INTEGER, FOREIGN KEY (user_id) REFERENCES users(id))",
        ["id", "user_id", "team_id"],
      ),
    ];

    expect(extractForeignKeys(tables)).toEqual([
      {
        fromTable: "orders",
        fromCol: "user_id",
        toTable: "users",
        toCol: "id",
      },
    ]);
  });
});

describe("computeLayout", () => {
  it("returns empty for no tables", () => {
    expect(computeLayout([])).toEqual([]);
  });

  it("places a single table at origin with width 160", () => {
    const layout = computeLayout([table("users", "CREATE TABLE users (id)")]);

    expect(layout).toEqual([
      { tableName: "users", x: 0, y: 0, width: 160, height: 25 + 1 * 12 + 4 },
    ]);
  });

  it("wraps to a new row when the next table exceeds the 220px column", () => {
    const layout = computeLayout([
      table("users", "CREATE TABLE users (id)"),
      table("orders", "CREATE TABLE orders (id)"),
    ]);

    expect(layout[0]).toMatchObject({ x: 0, y: 0 });
    expect(layout[1]).toMatchObject({
      x: 0,
      y: layout[0].height + 60,
    });
  });

  it("caps row height contribution at 8 columns", () => {
    const cols = Array.from({ length: 12 }, (_, i) => `col${i}`);
    const layout = computeLayout([table("wide", "CREATE TABLE wide", cols)]);

    expect(layout[0].height).toBe(25 + 8 * 12 + 4);
  });

  it("handles tables with no columns", () => {
    const layout = computeLayout([table("empty", "CREATE TABLE empty", [])]);

    expect(layout[0].height).toBe(25 + 0 * 12 + 4);
  });
});
