from __future__ import annotations

from pydantic import BaseModel


class MySQLConfigRequest(BaseModel):
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    db: str
    password: str = ""
    test_first: bool = True


class MySQLConfigResponse(BaseModel):
    ok: bool
    db_url: str
    host: str
    port: int
    user: str
    db: str
    mysql_password_set: bool
    message: str | None = None
    error_code: str | None = None
    error_type: str | None = None
