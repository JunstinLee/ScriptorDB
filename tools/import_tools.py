from __future__ import annotations

import csv
import os
from collections.abc import Callable
from typing import Any

from pydantic_ai import RunContext
from sqlalchemy import text

from config.settings import Settings
from logging_setup import get_logger
from tools.db_connection import get_connection
from tools.errors import _to_tool_error
from tools.tool_result import ToolErrorInfo, ToolResult


_log = get_logger("tools.import_tools")


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _table_exists(conn, table_name: str) -> bool:
    from sqlalchemy import inspect as sa_inspect

    return table_name in sa_inspect(conn).get_table_names()


def _create_table_from_headers(conn, table_name: str, headers: list[str]) -> None:
    cols_sql = [f"{_quote_identifier(header)} TEXT" for header in headers]
    sql = f"CREATE TABLE {_quote_identifier(table_name)} (\n  {',\n  '.join(cols_sql)}\n)"
    conn.execute(text(sql))


def _build_insert_sql(table_name: str, headers: list[str]) -> str:
    cols = [_quote_identifier(header) for header in headers]
    placeholders = [f":p{i}" for i in range(len(headers))]
    return (
        f"INSERT INTO {_quote_identifier(table_name)} "
        f"({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
    )


def _insert_batches(
    conn,
    table_name: str,
    headers: list[str],
    rows: list[list[Any]],
    batch_size: int,
) -> int:
    sql = _build_insert_sql(table_name, headers)
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        params = [
            {f"p{j}": row[j] for j in range(len(headers))}
            for row in batch
        ]
        conn.execute(text(sql), params)
        total += len(batch)
    return total


def _normalize_row(row: list[Any], length: int) -> list[Any]:
    if len(row) < length:
        return list(row) + [None] * (length - len(row))
    if len(row) > length:
        return row[:length]
    return list(row)


def _apply_hooks(
    rows: list[list[Any]],
    headers: list[str],
    row_filter: Callable[[dict[str, Any]], bool] | None,
    row_transform: Callable[[dict[str, Any]], dict[str, Any]] | None,
) -> list[list[Any]]:
    result: list[list[Any]] = []
    for row in rows:
        row = _normalize_row(row, len(headers))
        row_dict = dict(zip(headers, row))
        if row_filter is not None and not row_filter(row_dict):
            continue
        if row_transform is not None:
            row_dict = row_transform(row_dict)
        result.append([row_dict.get(header) for header in headers])
    return result


def _import_rows_to_db(
    ctx: RunContext[Settings],
    table_name: str,
    headers: list[str],
    rows: list[list[Any]],
    if_exists: str,
    batch_size: int,
) -> ToolResult:
    conn = get_connection(ctx.deps.db_url)
    try:
        exists = _table_exists(conn, table_name)
        if exists:
            if if_exists == "fail":
                _log.warning(
                    "import_rows: table exists and if_exists=fail table=%s", table_name
                )
                return ToolResult(
                    success=False,
                    error=ToolErrorInfo(
                        category="parameter_error",
                        message=f"Table '{table_name}' already exists",
                    ),
                )
            if if_exists == "replace":
                conn.execute(
                    text(f"DROP TABLE IF EXISTS {_quote_identifier(table_name)}")
                )
                conn.commit()
                _create_table_from_headers(conn, table_name, headers)
            elif if_exists == "append":
                pass
            else:
                _log.warning(
                    "import_rows: invalid if_exists=%s table=%s", if_exists, table_name
                )
                return ToolResult(
                    success=False,
                    error=ToolErrorInfo(
                        category="parameter_error",
                        message=f"Invalid if_exists value: {if_exists}",
                    ),
                )
        else:
            _create_table_from_headers(conn, table_name, headers)

        _log.info(
            "import_rows: start table=%s if_exists=%s cols=%d rows=%d batch_size=%d",
            table_name,
            if_exists,
            len(headers),
            len(rows),
            batch_size,
        )
        total_imported = _insert_batches(conn, table_name, headers, rows, batch_size)
        conn.commit()

        _log.info(
            "import_rows: done table=%s rows_imported=%d", table_name, total_imported
        )
        return ToolResult(
            success=True,
            output=f"Imported {total_imported} row{'s' if total_imported != 1 else ''} into {table_name}",
            data={
                "table": table_name,
                "columns": headers,
                "rows_imported": total_imported,
            },
        )
    except Exception as e:
        return _to_tool_error(e)
    finally:
        conn.close()


def _import_csv_to_db_impl(
    ctx: RunContext[Settings],
    filepath: str,
    table_name: str,
    encoding: str = "utf-8",
    if_exists: str = "fail",
    batch_size: int = 100,
    row_filter: Callable[[dict[str, Any]], bool] | None = None,
    row_transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> ToolResult:
    if not os.path.isfile(filepath):
        _log.warning("import_csv: file not found filepath=%s", filepath)
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="resource_not_found",
                message=f"File not found: {filepath}",
            ),
        )

    _log.info(
        "import_csv: start filepath=%s table=%s encoding=%s if_exists=%s batch_size=%d",
        filepath,
        table_name,
        encoding,
        if_exists,
        batch_size,
    )

    try:
        with open(filepath, "r", encoding=encoding, newline="") as f:
            reader = csv.reader(f)
            try:
                headers = [str(h) for h in next(reader)]
            except StopIteration:
                headers = []
            raw_rows = [row for row in reader]

        rows = _apply_hooks(raw_rows, headers, row_filter, row_transform)
        return _import_rows_to_db(ctx, table_name, headers, rows, if_exists, batch_size)
    except Exception as e:
        return _to_tool_error(e)


def import_csv_to_db(
    ctx: RunContext[Settings],
    filepath: str,
    table_name: str,
    encoding: str = "utf-8",
    if_exists: str = "fail",
    batch_size: int = 100,
) -> ToolResult:
    """Agent-visible entry point: imports a CSV file into the database."""
    return _import_csv_to_db_impl(
        ctx, filepath, table_name, encoding, if_exists, batch_size, None, None
    )


def _import_excel_to_db_impl(
    ctx: RunContext[Settings],
    filepath: str,
    table_name: str,
    sheet_name: str | int = 0,
    header_row: int = 1,
    if_exists: str = "fail",
    batch_size: int = 100,
    row_filter: Callable[[dict[str, Any]], bool] | None = None,
    row_transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> ToolResult:
    if not os.path.isfile(filepath):
        _log.warning("import_excel: file not found filepath=%s", filepath)
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="resource_not_found",
                message=f"File not found: {filepath}",
            ),
        )

    try:
        from openpyxl import load_workbook
    except ImportError:
        return ToolResult(
            success=False,
            error=ToolErrorInfo(
                category="parameter_error",
                message="openpyxl is not installed. Run: uv sync",
            ),
        )

    _log.info(
        "import_excel: start filepath=%s table=%s sheet=%s header_row=%d if_exists=%s batch_size=%d",
        filepath,
        table_name,
        sheet_name,
        header_row,
        if_exists,
        batch_size,
    )

    try:
        wb = load_workbook(filepath, data_only=True, read_only=True)
        if isinstance(sheet_name, int):
            if sheet_name < 0 or sheet_name >= len(wb.worksheets):
                return ToolResult(
                    success=False,
                    error=ToolErrorInfo(
                        category="parameter_error",
                        message=f"Sheet index {sheet_name} out of range",
                    ),
                )
            ws = wb.worksheets[sheet_name]
        else:
            if sheet_name not in wb.sheetnames:
                return ToolResult(
                    success=False,
                    error=ToolErrorInfo(
                        category="parameter_error",
                        message=f"Sheet '{sheet_name}' not found",
                    ),
                )
            ws = wb[sheet_name]

        rows_iter = ws.iter_rows(min_row=header_row, values_only=True)
        try:
            headers = [str(h) if h is not None else "" for h in next(rows_iter)]
        except StopIteration:
            headers = []
        raw_rows = [list(row) for row in rows_iter]
        wb.close()

        rows = _apply_hooks(raw_rows, headers, row_filter, row_transform)
        return _import_rows_to_db(ctx, table_name, headers, rows, if_exists, batch_size)
    except Exception as e:
        return _to_tool_error(e)


def import_excel_to_db(
    ctx: RunContext[Settings],
    filepath: str,
    table_name: str,
    sheet_name: str | int = 0,
    header_row: int = 1,
    if_exists: str = "fail",
    batch_size: int = 100,
) -> ToolResult:
    """Agent-visible entry point: imports an Excel file into the database."""
    return _import_excel_to_db_impl(
        ctx,
        filepath,
        table_name,
        sheet_name,
        header_row,
        if_exists,
        batch_size,
        None,
        None,
    )
