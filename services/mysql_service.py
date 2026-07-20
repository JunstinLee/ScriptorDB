from __future__ import annotations

from pathlib import Path
from typing import Any

import pymysql

from agents.db_agent import reset_agent_cache
from config.secrets import save_mysql_password
from config.settings import load_for_workspace
from config.workspace import WorkspaceSettings
from database.session import clear_pools
from server.schemas import MySQLConfigResponse


def test_connection(host: str, port: int, user: str, password: str, db: str) -> tuple[bool, str | None, str]:
    try:
        with pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=db,
            charset="utf8mb4",
            connect_timeout=10,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True, None, ""
    except pymysql.OperationalError as e:
        code, etype, msg = _classify_operational_error(e)
        return False, code, msg
    except pymysql.ProgrammingError as e:
        return False, "programming_error", str(e)
    except pymysql.InternalError as e:
        return False, "internal_error", str(e)
    except pymysql.IntegrityError as e:
        return False, "integrity_error", str(e)
    except pymysql.Error as e:
        return False, "unknown_error", str(e)


def configure_mysql(
    rec: Any,
    host: str,
    port: int,
    user: str,
    password: str,
    db: str,
    config: Any,
) -> MySQLConfigResponse:
    db_url = f"mysql+pymysql://{user}@{host}:{port}/{db}"
    ws_settings = WorkspaceSettings.load(Path(rec.path), rec.id, rec.name)
    ws_settings.db_url = db_url
    ws_settings.mysql_host = host
    ws_settings.mysql_port = port
    ws_settings.mysql_user = user
    ws_settings.mysql_db = db
    ws_settings.mysql_password_set = bool(password)
    ws_settings.save()

    save_mysql_password(rec.id, password)
    clear_pools()

    if config.workspace_id == rec.id:
        load_for_workspace(config, rec.id)
        reset_agent_cache()

    return MySQLConfigResponse(
        ok=True,
        db_url=db_url,
        host=host,
        port=port,
        user=user,
        db=db,
        mysql_password_set=bool(password),
        message="MySQL configuration saved",
    )


def reset_mysql_to_sqlite(rec: Any, config: Any) -> MySQLConfigResponse:
    ws_settings = WorkspaceSettings.load(Path(rec.path), rec.id, rec.name)
    ws_settings.db_url = f"sqlite:///{Path(rec.path) / 'scriptordb.sqlite'}"
    ws_settings.save()

    clear_pools()

    if config.workspace_id == rec.id:
        load_for_workspace(config, rec.id)
        reset_agent_cache()

    return MySQLConfigResponse(
        ok=True,
        db_url=ws_settings.db_url,
        host=ws_settings.mysql_host,
        port=ws_settings.mysql_port,
        user=ws_settings.mysql_user,
        db=ws_settings.mysql_db,
        mysql_password_set=ws_settings.mysql_password_set,
        message="Switched to SQLite (MySQL configuration preserved)",
    )


def build_error_response(
    host: str,
    port: int,
    user: str,
    db: str,
    password_set: bool,
    error_code: str,
    error_type: str,
    message: str,
) -> MySQLConfigResponse:
    return MySQLConfigResponse(
        ok=False,
        db_url="",
        host=host,
        port=port,
        user=user,
        db=db,
        mysql_password_set=password_set,
        message=message,
        error_code=error_code,
        error_type=error_type,
    )


def _classify_operational_error(e: pymysql.OperationalError) -> tuple[str, str, str]:
    code = e.args[0] if len(e.args) > 0 else None
    if code in (1045, 1044):
        return "access_denied", "operational_error", str(e)
    if code == 1049:
        return "unknown_database", "operational_error", str(e)
    if code in (2003, 2005):
        return "connection_failed", "operational_error", str(e)
    return "operational_error", "operational_error", str(e)
