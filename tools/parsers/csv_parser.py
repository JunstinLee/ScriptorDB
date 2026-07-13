from __future__ import annotations

import csv
import os
from collections.abc import Callable
from typing import Any


def parse_csv(
    filepath: str,
    encoding: str = "utf-8",
    row_filter: Callable[[dict[str, Any]], bool] | None = None,
    row_transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> tuple[list[str], list[list[Any]], str | None]:
    if not os.path.isfile(filepath):
        return [], [], f"File not found: {filepath}"

    try:
        with open(filepath, "r", encoding=encoding, newline="") as f:
            reader = csv.reader(f)
            try:
                headers = [str(h) for h in next(reader)]
            except StopIteration:
                headers = []
            raw_rows = [row for row in reader]
    except Exception as e:
        return [], [], str(e)

    rows = _apply_hooks(raw_rows, headers, row_filter, row_transform)
    return headers, rows, None


def count_csv_rows(filepath: str) -> int | None:
    if not filepath or not os.path.isfile(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            try:
                next(reader)
            except StopIteration:
                return 0
            return sum(1 for _ in reader)
    except Exception:
        return None


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
