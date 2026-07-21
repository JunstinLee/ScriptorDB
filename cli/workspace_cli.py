from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from agents.db_agent import reset_agent_cache
from cli import app
from cli.cmd_common import _get_config_ctx
from config.settings import load_for_workspace
from config.workspace import (
    WorkspaceAlreadyExistsError,
    WorkspaceNotFoundError,
    WorkspaceRegistry,
    migrate_legacy,
)


workspace_app = typer.Typer(help="工作区管理命令")
app.add_typer(workspace_app, name="workspace")


@workspace_app.command("list")
def workspace_list():
    """列出所有工作区。"""
    migrate_legacy()
    registry = WorkspaceRegistry()
    recs = registry.list()
    config = _get_config_ctx()
    if not recs:
        typer.echo("还没有任何工作区。使用 'workspace create' 创建一个。")
        return
    typer.echo("工作区列表：\n")
    for i, rec in enumerate(recs, 1):
        marker = " *" if rec.id == config.workspace_id else "  "
        typer.echo(f"{marker} {i}. {rec.name}  [{rec.id}]")
        typer.echo(f"      path: {rec.path}")
    if config.workspace_id:
        typer.echo("\n* = 当前激活")


@workspace_app.command("create")
def workspace_create(
    path: Annotated[str, typer.Argument(help="工作区目录的绝对路径")],
    name: Annotated[Optional[str], typer.Option("--name", "-n")] = None,
    db_url: Annotated[Optional[str], typer.Option("--db-url")] = None,
):
    """创建一个新工作区。"""
    target = Path(path).expanduser()
    if not target.exists() or not target.is_dir():
        typer.echo(f"目录不存在或不是目录: {target}", err=True)
        raise typer.Exit(1)
    registry = WorkspaceRegistry()
    try:
        rec = registry.create(target, name=name, db_url=db_url)
    except WorkspaceAlreadyExistsError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    typer.echo(f"已创建工作区: {rec.name} ({rec.id})")


@workspace_app.command("switch")
def workspace_switch(
    workspace_id: Annotated[str, typer.Argument(help="工作区 ID 或名称")],
):
    """切换当前工作区。"""
    config = _get_config_ctx()
    registry = WorkspaceRegistry()
    rec = _resolve_workspace(registry, workspace_id)
    load_for_workspace(config, rec.id)
    registry.set_last_active(rec.id)
    reset_agent_cache()
    typer.echo(f"已切换到工作区: {rec.name} ({rec.id})")


@workspace_app.command("current")
def workspace_current():
    """显示当前工作区。"""
    config = _get_config_ctx()
    if not config.workspace_id:
        typer.echo("当前没有激活的工作区。", err=True)
        raise typer.Exit(1)
    typer.echo(f"工作区: {config.workspace_name} ({config.workspace_id})")
    typer.echo(f"路径:   {config.workspace_path}")
    typer.echo(f"DB:     {config.db_url}")
    typer.echo(f"LLM:    {config.llm_provider} / {config.llm_model or '(default)'}")


@workspace_app.command("rename")
def workspace_rename(
    workspace_id: Annotated[str, typer.Argument(help="工作区 ID 或名称")],
    new_name: Annotated[str, typer.Argument(help="新名称")],
):
    """重命名工作区。"""
    registry = WorkspaceRegistry()
    rec = _resolve_workspace(registry, workspace_id)
    rec = registry.rename(rec.id, new_name)
    typer.echo(f"已重命名: {rec.name} ({rec.id})")


@workspace_app.command("remove")
def workspace_remove(
    workspace_id: Annotated[str, typer.Argument(help="工作区 ID 或名称")],
    delete_files: Annotated[bool, typer.Option("--delete-files")] = False,
):
    """从注册表移除工作区（可选同时删除目录下的 .scriptordb/）。"""
    config = _get_config_ctx()
    registry = WorkspaceRegistry()
    rec = _resolve_workspace(registry, workspace_id)
    was_active = config.workspace_id == rec.id
    registry.remove(rec.id, delete_files=delete_files)
    if was_active:
        config.clear()
        reset_agent_cache()
    typer.echo(f"已移除工作区: {rec.name} ({rec.id})")


@workspace_app.command("migrate")
def workspace_migrate():
    """手动触发从旧全局 config 迁移到工作区。"""
    rec = migrate_legacy()
    if rec is None:
        typer.echo("工作区已存在，无需迁移。")
    else:
        typer.echo(f"已迁移并创建默认工作区: {rec.name} ({rec.id})")


def _resolve_workspace(registry: WorkspaceRegistry, ident: str):
    try:
        return registry.get(ident)
    except WorkspaceNotFoundError:
        for rec in registry.list():
            if rec.name == ident:
                return rec
        typer.echo(f"找不到工作区: {ident}", err=True)
        raise typer.Exit(1)
