from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.models import fuzzy_match_model
from logging_setup import get_logger
from tools.parsers.csv_parser import count_csv_rows
from tools.parsers.excel_parser import count_excel_rows

_log = get_logger("server.import_inspector")


def count_import_rows(filepath: str) -> int | None:
    ext = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""
    if ext == "csv":
        return count_csv_rows(filepath)
    if ext in {"xlsx", "xls"}:
        return count_excel_rows(filepath)
    return None
