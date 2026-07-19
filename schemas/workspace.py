from __future__ import annotations

from pydantic import BaseModel


class WorkspaceCreateRequest(BaseModel):
    name: str | None = None
    path: str | None = None
    db_url: str | None = None


class WorkspaceActivateRequest(BaseModel):
    workspace_id: str | None = None


class WorkspaceItem(BaseModel):
    id: str
    name: str
    path: str
    created_at: str
    is_active: bool = False


class WorkspaceDetail(WorkspaceItem):
    db_url: str
    llm_provider: str
    llm_model: str | None = None
    mysql_host: str | None = None
    mysql_port: int | None = None
    mysql_user: str | None = None
    mysql_db: str | None = None
    mysql_password_set: bool = False


class WorkspaceListResponse(BaseModel):
    workspaces: list[WorkspaceItem]
    active_workspace_id: str | None = None


class ActiveWorkspaceResponse(BaseModel):
    workspace: WorkspaceDetail | None = None


class WorkspaceDeleteResponse(BaseModel):
    ok: bool
    deleted_files: bool = False
