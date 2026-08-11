from __future__ import annotations

"""Database access layer.

- `session.py` — MySQL connection pool (DBUtils + PyMySQL), used by mysql_service
- `repository.py` — SQLAlchemy engine pool + `DatabaseRepository` (SQLite/MySQL/PostgreSQL)
- `connection.py` — standalone SQLAlchemy engine/connection/schema helpers
"""

from database.repository import DatabaseRepository, EnginePool

__all__ = ["DatabaseRepository", "EnginePool"]
