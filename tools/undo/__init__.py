from __future__ import annotations

"""Undo: run-group tracking and revert for DB write operations.

Single entry point for undo functionality:
- `UndoManager` — per-run lifecycle used by agent capabilities (agents/capabilities.py)
- `UndoRepository` — SQL storage for undo groups/entries (SQLite/PostgreSQL/MySQL)
"""

from tools.undo.manager import UndoManager
from tools.undo.repository import UndoRepository

__all__ = ["UndoManager", "UndoRepository"]
